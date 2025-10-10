from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import os
import bcrypt
import jwt
import requests
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
from bs4 import BeautifulSoup
from urllib.parse import quote
from dotenv import load_dotenv
from pathlib import Path
import re
import random
import time

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configurações
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'verificapessoa')
JWT_SECRET = os.environ.get('JWT_SECRET', 'verificapessoa_secret_2025')
MP_PUBLIC_KEY = "APP_USR-aff32c11-93e2-4ed5-8a5a-9e2ca4405766"
MP_ACCESS_TOKEN = "APP_USR-6850941285056243-092512-017e23d3c41ef7b0c005df7970bf13a1-94875335"
PIX_KEY = "3656e000-acb3-4645-a176-034c4d9ba6df"
PIX_NAME = "Verifica Pessoa"

app = FastAPI(title="VerificaPessoa API", version="1.0.0")

@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://verificapessoa.com", "https://www.verificapessoa.com", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

client = None
db = None

@app.on_event("startup")
async def startup_db_client():
    global client, db
    try:
        client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000, connectTimeoutMS=10000, socketTimeoutMS=10000, tls=True, tlsAllowInvalidCertificates=True)
        await client.admin.command('ping')
        db = client[DB_NAME]
        print(f"✅ MongoDB conectado: {DB_NAME}")
    except Exception as e:
        print(f"❌ ERRO MongoDB: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    credits: int
    created_at: datetime

class SearchRequest(BaseModel):
    name: str
    
class PurchaseRequest(BaseModel):
    package_type: str
    amount: float
    credits: int

# BUSCA PROFUNDA MELHORADA
class RealPersonSearch:
    def __init__(self):
        self.timeout = 30
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]
    
    def get_headers(self):
        """Headers realistas com user-agent rotativo"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        }
    
    async def search_google(self, query: str, max_retries: int = 3) -> List[Dict[str, Any]]:
        """Busca no Google com retry e detecção de bloqueio"""
        
        for attempt in range(max_retries):
            try:
                encoded_query = quote(query)
                url = f'https://www.google.com/search?q={encoded_query}&num=50&hl=pt-BR'
                
                # Delay randomizado (parecer humano)
                delay = random.uniform(2.0, 4.0)
                await asyncio.sleep(delay)
                
                print(f"    🌐 Tentativa {attempt + 1}/{max_retries}: {query[:60]}...")
                
                headers = self.get_headers()
                response = requests.get(url, headers=headers, timeout=self.timeout)
                
                # Verificar bloqueio
                if response.status_code == 429:
                    print(f"    ⚠️ Rate limit - aguardando {10 * (attempt + 1)}s...")
                    await asyncio.sleep(10 * (attempt + 1))
                    continue
                
                if response.status_code != 200:
                    print(f"    ❌ Status {response.status_code}")
                    continue
                
                # Verificar se foi bloqueado (captcha, etc)
                if 'www.google.com/sorry' in response.url or 'captcha' in response.text.lower():
                    print(f"    🚫 BLOQUEIO DETECTADO - Aguardando...")
                    await asyncio.sleep(15 * (attempt + 1))
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Verificar se tem resultados
                if not soup.find('body'):
                    print(f"    ❌ HTML vazio ou inválido")
                    continue
                
                results = []
                
                # Múltiplos seletores (Google muda frequentemente)
                search_divs = (
                    soup.find_all('div', class_='g') or
                    soup.find_all('div', class_='tF2Cxc') or
                    soup.find_all('div', {'data-sokoban-container': True}) or
                    soup.select('div[data-hveid]')
                )
                
                print(f"    📦 Encontrados {len(search_divs)} elementos div")
                
                for div in search_divs:
                    # Tentar múltiplos seletores para título
                    title_elem = (
                        div.find('h3') or
                        div.find('div', class_='BNeawe vvjwJb AP7Wnd') or
                        div.select_one('h3.LC20lb')
                    )
                    
                    # Tentar múltiplos seletores para snippet
                    snippet_elem = (
                        div.find('div', class_='VwiC3b') or
                        div.find('div', class_='BNeawe s3v9rd AP7Wnd') or
                        div.find('span', class_='aCOpRe') or
                        div.select_one('div.IsZvec')
                    )
                    
                    # Tentar pegar link
                    link_elem = div.find('a', href=True)
                    
                    if title_elem:
                        title = title_elem.get_text().strip()
                        snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                        url = link_elem['href'] if link_elem else ""
                        
                        # Limpar URL do Google
                        if url.startswith('/url?q='):
                            url = url.split('/url?q=')[1].split('&')[0]
                        
                        if title and len(title) > 3:
                            results.append({
                                "query": query,
                                "title": title[:300],
                                "snippet": snippet[:500],
                                "url": url[:500]
                            })
                
                print(f"    ✅ Extraídos {len(results)} resultados válidos")
                
                if len(results) > 0:
                    return results
                else:
                    print(f"    ⚠️ Nenhum resultado extraído - tentando novamente...")
                    
            except Exception as e:
                print(f"    ❌ Erro na tentativa {attempt + 1}: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
        
        print(f"    ❌ FALHOU após {max_retries} tentativas")
        return []
    
    async def extract_info_from_google(self, name: str) -> Dict[str, Any]:
        """BUSCA PROFUNDA com 10 queries + retry + detecção de bloqueio"""
        
        print(f"\n{'='*80}")
        print(f"🔍 INICIANDO BUSCA PROFUNDA: {name}")
        print(f"{'='*80}\n")
        
        queries = [
            f'"{name}"',
            f'"{name}" Brasil',
            f'"{name}" processos',
            f'"{name}" jusbrasil',
            f'"{name}" CNPJ',
            f'"{name}" empresa',
            f'"{name}" LinkedIn',
            f'"{name}" Facebook',
            f'"{name}" Instagram',
            f'"{name}" notícias',
        ]
        
        all_results = []
        all_text = ""
        
        for i, query in enumerate(queries):
            print(f"\n📊 Query {i+1}/{len(queries)}: {query}")
            
            results = await self.search_google(query)
            
            if results:
                all_results.extend(results)
                for r in results:
                    all_text += " " + r['title'].lower() + " " + r['snippet'].lower()
                print(f"✅ Total acumulado: {len(all_results)} resultados")
            else:
                print(f"⚠️ Query sem resultados")
        
        print(f"\n{'='*80}")
        print(f"📊 ANÁLISE COMPLETA: {len(all_results)} resultados de {len(queries)} queries")
        print(f"{'='*80}\n")
        
        # ANÁLISE DOS DADOS
        
        # 1. PROCESSOS
        print("⚖️ Analisando processos judiciais...")
        processos = []
        processo_count = 0
        
        # Procurar padrões de processos
        processo_patterns = [
            r'(\d+)\s*processo[s]?',
            r'processo[s]?\s*(?:n[°º]?)?\s*(\d+)',
            r'(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})',
        ]
        
        for pattern in processo_patterns:
            matches = re.findall(pattern, all_text)
            for match in matches:
                if isinstance(match, str) and match.isdigit():
                    num = int(match)
                    if 0 < num < 1000 and num > processo_count:
                        processo_count = num
        
        # Processos detalhados
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            if any(word in text.lower() for word in ['processo', 'ação', 'tribunal', 'juiz', 'sentença', 'julgamento', 'recurso']):
                
                tribunal = "Não especificado"
                if 'tjsp' in text.lower(): tribunal = "TJSP"
                elif 'tjrj' in text.lower(): tribunal = "TJRJ"
                elif 'trf' in text.lower(): tribunal = "TRF"
                elif 'stj' in text.lower(): tribunal = "STJ"
                
                tipo = "Processo Judicial"
                if 'trabalhista' in text.lower(): tipo = "Trabalhista"
                elif 'civil' in text.lower(): tipo = "Cível"
                
                processos.append({
                    "type": tipo,
                    "title": result['title'][:250],
                    "description": result['snippet'][:400],
                    "tribunal": tribunal,
                    "source": "Google/Jusbrasil",
                    "url": result['url']
                })
        
        if processo_count > 0:
            processos.insert(0, {
                "type": "📊 RESUMO",
                "title": f"⚖️ {processo_count} PROCESSO(S) ENCONTRADO(S)",
                "description": f"Total de {len(processos)} registros judiciais identificados",
                "source": "Análise Google",
                "note": "Verificar em CNJ, Jusbrasil ou tribunais estaduais"
            })
        
        print(f"✅ {len(processos)} processos identificados (count: {processo_count})")
        
        # 2. EMPRESAS
        print("🏢 Analisando vínculos empresariais...")
        empresas = []
        
        cnpj_pattern = r'\d{2}\.?\d{3}\.?\d{3}[/]?\d{4}[-]?\d{2}'
        cnpjs = re.findall(cnpj_pattern, all_text)
        
        for cnpj in list(set(cnpjs))[:10]:
            empresas.append({
                "type": "🏢 CNPJ",
                "company": f"CNPJ: {cnpj}",
                "cnpj": cnpj,
                "source": "Google",
                "note": "Consultar Receita Federal"
            })
        
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            if any(word in text.lower() for word in ['cnpj', 'empresa', 'sócio', 'mei', 'ltda']):
                
                vinculo = "Empresa"
                if 'sócio' in text.lower(): vinculo = "Sócio"
                elif 'administrador' in text.lower(): vinculo = "Administrador"
                elif 'mei' in text.lower(): vinculo = "MEI"
                
                empresas.append({
                    "type": f"💼 {vinculo}",
                    "company": result['title'][:200],
                    "details": result['snippet'][:300],
                    "source": "Google",
                    "url": result['url']
                })
        
        print(f"✅ {len(empresas)} vínculos empresariais ({len(cnpjs)} CNPJs)")
        
        # 3. REDES SOCIAIS
        print("📱 Analisando redes sociais...")
        social_media = []
        
        linkedin_urls = re.findall(r'linkedin\.com/in/([\w-]+)', all_text)
        for username in set(linkedin_urls[:5]):
            social_media.append({
                "platform": "💼 LinkedIn",
                "profile": username,
                "url": f"https://www.linkedin.com/in/{username}",
                "status": "Perfil encontrado"
            })
        
        facebook_urls = re.findall(r'facebook\.com/([\w.]+)', all_text)
        for username in set(facebook_urls[:5]):
            if username not in ['pages', 'groups', 'watch', 'share']:
                social_media.append({
                    "platform": "📘 Facebook",
                    "profile": username,
                    "url": f"https://www.facebook.com/{username}",
                    "status": "Perfil encontrado"
                })
        
        instagram_urls = re.findall(r'instagram\.com/([\w.]+)', all_text)
        for username in set(instagram_urls[:5]):
            if username not in ['explore', 'p', 'reel']:
                social_media.append({
                    "platform": "📷 Instagram",
                    "profile": f"@{username}",
                    "url": f"https://www.instagram.com/{username}",
                    "status": "Perfil encontrado"
                })
        
        print(f"✅ {len(social_media)} perfis sociais")
        
        # 4. FAMÍLIA
        print("👥 Analisando informações familiares...")
        family_info = []
        family_keywords = {'filho': '👦 Filho', 'filha': '👧 Filha', 'pai': '👨 Pai', 'mãe': '👩 Mãe', 'esposa': '💑 Esposa', 'marido': '💑 Marido', 'irmão': '👬 Irmão', 'irmã': '👭 Irmã'}
        
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            for keyword, tipo in family_keywords.items():
                if keyword in text.lower():
                    family_info.append({
                        "type": tipo,
                        "details": result['snippet'][:250],
                        "source": "Google",
                        "note": "Verificar manualmente"
                    })
                    if len(family_info) >= 8: break
            if len(family_info) >= 8: break
        
        print(f"✅ {len(family_info)} menções familiares")
        
        # 5. OUTRAS INFORMAÇÕES
        print("📰 Analisando outras informações...")
        public_records = []
        
        for result in all_results[:30]:
            categoria = "📋 Menção"
            if any(w in result['url'].lower() for w in ['g1.com', 'uol.com', 'folha', 'estadao']):
                categoria = "📰 Notícia"
            elif any(w in result['snippet'].lower() for w in ['atleta', 'esporte', 'competição']):
                categoria = "🏃 Esporte"
            
            public_records.append({
                "source": categoria,
                "title": result['title'][:200],
                "snippet": result['snippet'][:350],
                "url": result['url']
            })
        
        print(f"✅ {len(public_records)} registros públicos")
        
        print(f"\n{'='*80}")
        print(f"✅ BUSCA CONCLUÍDA COM SUCESSO!")
        print(f"{'='*80}\n")
        
        return {
            "processos": processos,
            "processo_count": processo_count,
            "empresas": empresas,
            "social_media": social_media,
            "public_records": public_records,
            "family_info": family_info,
            "total_results": len(all_results)
        }
    
    async def search_person(self, full_name: str) -> Dict[str, Any]:
        """Busca principal"""
        
        extracted = await self.extract_info_from_google(full_name)
        
        social_media = extracted["social_media"] if extracted["social_media"] else [{
            "platform": "Não encontrado",
            "profile": "Nenhum perfil público encontrado",
            "status": "Não encontrado"
        }]
        
        legal_records = extracted["processos"] if extracted["processos"] else [{
            "type": "Processos",
            "title": "Nenhum processo encontrado",
            "source": "Google",
            "note": "Verificar manualmente em portais oficiais"
        }]
        
        professional = extracted["empresas"] if extracted["empresas"] else [{
            "type": "Empresas",
            "company": "Nenhum vínculo empresarial encontrado",
            "source": "Google"
        }]
        
        family_info = extracted["family_info"] if extracted["family_info"] else [{
            "type": "Família",
            "details": "Informações familiares não disponíveis",
            "note": "Requer registros civis"
        }]
        
        public_records = extracted["public_records"] if extracted["public_records"] else [{
            "source": "Google",
            "title": "Informações limitadas",
            "snippet": "Verificar outras fontes"
        }]
        
        return {
            "name": full_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources_searched": 10,
            "profiles_found": extracted["total_results"],
            "social_media": social_media,
            "legal_records": legal_records,
            "professional": professional,
            "family_info": family_info,
            "public_records": public_records,
            "risk_assessment": "baixo" if len(legal_records) <= 1 else "médio",
            "disclaimer": "⚠️ IMPORTANTE: Informações de fontes públicas. Verificação cruzada obrigatória. Podem existir homônimos."
        }

search_system = RealPersonSearch()

# Funções utilitárias
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_jwt_token(user_data: dict) -> str:
    payload = {"user_id": user_data["_id"], "email": user_data["email"], "exp": datetime.utcnow() + timedelta(days=30)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def get_current_user(authorization: Optional[str] = Header(None, alias="Authorization")):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token necessário")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user = await db.users.find_one({"_id": payload["user_id"]})
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ROTAS
@app.post("/api/auth/register")
async def register_user(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    user_id = str(uuid.uuid4())
    new_user = {"_id": user_id, "email": user_data.email, "password": hash_password(user_data.password), "credits": 0, "created_at": datetime.now(timezone.utc)}
    await db.users.insert_one(new_user)
    return {"message": "Usuário criado", "user": UserResponse(id=user_id, email=user_data.email, credits=0, created_at=new_user["created_at"])}

@app.post("/api/auth/login")
async def login_user(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")
    return {"token": create_jwt_token(user), "user": UserResponse(id=user["_id"], email=user["email"], credits=user.get("credits", 0), created_at=user["created_at"])}

@app.post("/api/search")
async def search_person(search_data: SearchRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("credits", 0) < 1:
        raise HTTPException(status_code=400, detail="Créditos insuficientes")
    results = await search_system.search_person(search_data.name)
    await db.users.update_one({"_id": current_user["_id"]}, {"$inc": {"credits": -1}})
    await db.searches.insert_one({"_id": str(uuid.uuid4()), "user_email": current_user["email"], "search_name": search_data.name, "results": results, "created_at": datetime.now(timezone.utc)})
    return results

@app.post("/api/purchase")
async def create_purchase(purchase_data: PurchaseRequest, current_user: dict = Depends(get_current_user)):
    transaction_id = str(uuid.uuid4())
    await db.transactions.insert_one({"_id": transaction_id, "user_email": current_user["email"], "package_type": purchase_data.package_type, "amount": purchase_data.amount, "credits": purchase_data.credits, "status": "pending", "created_at": datetime.now(timezone.utc)})
    return {"transaction_id": transaction_id, "pix_info": {"key": PIX_KEY, "name": PIX_NAME, "amount": purchase_data.amount}}

@app.get("/api/admin/stats")
async def get_admin_stats():
    total_users = await db.users.count_documents({})
    total_searches = await db.searches.count_documents({})
    confirmed = await db.transactions.find({"status": "confirmed"}).to_list(None)
    return {"total_users": total_users, "total_searches": total_searches, "total_revenue": sum(t["amount"] for t in confirmed), "today_sales": 0}

@app.get("/api/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    return UserResponse(id=current_user["_id"], email=current_user["email"], credits=current_user.get("credits", 0), created_at=current_user["created_at"])

@app.get("/api/admin/users")
async def get_all_users():
    users = await db.users.find({}, {"password": 0}).to_list(None)
    return {"users": users, "total": len(users)}

@app.get("/api/admin/transactions")
async def get_all_transactions():
    transactions = await db.transactions.find({}).to_list(None)
    return {"transactions": transactions, "total": len(transactions)}

@app.get("/api/admin/searches")
async def get_all_searches():
    searches = await db.searches.find({}).to_list(None)
    return {"searches": searches, "total": len(searches)}

@app.post("/api/admin/add-credits")
async def add_credits_to_user(data: dict):
    result = await db.users.update_one({"email": data.get("email")}, {"$inc": {"credits": int(data.get("credits", 0))}})
    if result.matched_count > 0:
        return {"success": True, "message": f"{data.get('credits')} créditos adicionados"}
    raise HTTPException(status_code=404, detail="Usuário não encontrado")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}

@app.get("/")
async def root():
    return {"message": "VerificaPessoa API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))

