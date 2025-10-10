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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configurações do banco de dados
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'verificapessoa')
JWT_SECRET = os.environ.get('JWT_SECRET', 'verificapessoa_secret_2025')

# Configurações Mercado Pago
MP_PUBLIC_KEY = "APP_USR-aff32c11-93e2-4ed5-8a5a-9e2ca4405766"
MP_ACCESS_TOKEN = "APP_USR-6850941285056243-092512-017e23d3c41ef7b0c005df7970bf13a1-94875335"

# Configurações PIX
PIX_KEY = "3656e000-acb3-4645-a176-034c4d9ba6df"
PIX_NAME = "Verifica Pessoa"

app = FastAPI(title="VerificaPessoa API", version="1.0.0")

# Middleware personalizado para garantir CORS
@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# CORS - CONFIGURAÇÃO CORRIGIDA
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://verificapessoa.com",
        "https://www.verificapessoa.com",
        "http://localhost:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Conexão MongoDB
client = None
db = None

@app.on_event("startup")
async def startup_db_client():
    global client, db
    try:
        # Configuração SSL melhorada para MongoDB
        client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            tls=True,
            tlsAllowInvalidCertificates=True
        )
        # Testar conexão
        await client.admin.command('ping')
        db = client[DB_NAME]
        print(f"✅ MongoDB conectado: {DB_NAME}")
    except Exception as e:
        print(f"❌ ERRO ao conectar MongoDB: {e}")
        print(f"❌ MONGO_URL: {MONGO_URL[:50]}...")
        raise

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Modelos Pydantic
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

# Sistema de Busca Real PROFUNDO - 10 QUERIES
class RealPersonSearch:
    def __init__(self):
        self.timeout = 30
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
    
    async def extract_info_from_google(self, name: str) -> Dict[str, Any]:
        """BUSCA PROFUNDA: 10 queries diferentes no Google"""
        
        print(f"🔍 Iniciando BUSCA PROFUNDA por '{name}'...")
        
        # ========== 10 QUERIES DIFERENTES ==========
        queries = [
            f'"{name}"',
            f'"{name}" processos judiciais',
            f'"{name}" CNPJ empresa',
            f'"{name}" LinkedIn',
            f'"{name}" Facebook',
            f'"{name}" Instagram',
            f'"{name}" notícias',
            f'"{name}" tribunal justiça',
            f'"{name}" sócio administrador',
            f'"{name}" família esposa filho',
        ]
        
        all_results = []
        all_text = ""
        
        for i, query in enumerate(queries):
            print(f"  📊 Query {i+1}/10: {query[:50]}...")
            
            try:
                encoded_query = quote(query)
                url = f'https://www.google.com/search?q={encoded_query}&num=50&hl=pt-BR'
                
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    all_text += " " + soup.get_text().lower()
                    
                    search_divs = soup.find_all('div', class_='g') or soup.find_all('div', class_='tF2Cxc')
                    
                    for result in search_divs:
                        title_elem = result.find('h3')
                        snippet_elem = (
                            result.find('div', class_='VwiC3b') or
                            result.find('div', class_='BNeawe s3v9rd AP7Wnd')
                        )
                        link_elem = result.find('a')
                        
                        if title_elem:
                            all_results.append({
                                "query": query,
                                "title": title_elem.get_text().strip(),
                                "snippet": snippet_elem.get_text().strip()[:400] if snippet_elem else "",
                                "url": link_elem.get('href') if link_elem else ""
                            })
                
                await asyncio.sleep(1.5)
                
            except Exception as e:
                print(f"  ❌ Erro na query {i+1}: {e}")
                continue
        
        print(f"  ✅ Coletados {len(all_results)} resultados de {len(queries)} buscas")
        
        page_text = all_text
        
        # ========== ANÁLISE PROFUNDA ==========
        
        print("  🔍 Analisando processos judiciais...")
        
        # 1. PROCESSOS JUDICIAIS
        processos = []
        processos_detalhados = []
        
        processo_patterns = [
            r'(\d+)\s*processo[s]?',
            r'processo[s]?\s*n[°º]?\s*(\d+)',
            r'(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})',
            r'ação\s*[\w\s]*?n[°º]?\s*(\d+)',
        ]
        
        processo_count = 0
        numeros_processo = []
        
        for pattern in processo_patterns:
            matches = re.findall(pattern, page_text)
            for match in matches:
                if isinstance(match, str):
                    if match.isdigit():
                        num = int(match)
                        if num > processo_count and num < 1000:
                            processo_count = num
                    elif '-' in match:
                        numeros_processo.append(match)
        
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            
            if any(word in text.lower() for word in ['processo', 'ação', 'tribunal', 'juiz', 'sentença', 'recurso', 'apelação', 'julgamento']):
                
                tribunal = "Tribunal não identificado"
                if 'tjsp' in text.lower() or 'tribunal de justiça de são paulo' in text.lower():
                    tribunal = "TJSP"
                elif 'tjrj' in text.lower():
                    tribunal = "TJRJ"
                elif 'stj' in text.lower():
                    tribunal = "STJ"
                elif 'stf' in text.lower():
                    tribunal = "STF"
                elif 'trt' in text.lower():
                    tribunal = "TRT"
                
                tipo_acao = "Não especificado"
                if 'trabalhista' in text.lower():
                    tipo_acao = "Ação Trabalhista"
                elif 'civil' in text.lower():
                    tipo_acao = "Ação Cível"
                elif 'criminal' in text.lower():
                    tipo_acao = "Ação Criminal"
                elif 'execução' in text.lower():
                    tipo_acao = "Execução"
                
                processos_detalhados.append({
                    "type": tipo_acao,
                    "title": result['title'][:250],
                    "description": result['snippet'][:400],
                    "tribunal": tribunal,
                    "source": "Jusbrasil / Google",
                    "url": result['url'] if 'jusbrasil' in result['url'] else None
                })
        
        if processo_count > 0 or len(numeros_processo) > 0:
            processos.append({
                "type": f"📊 RESUMO PROCESSOS",
                "title": f"⚖️ Aproximadamente {processo_count if processo_count > 0 else len(numeros_processo)} PROCESSO(S) ENCONTRADO(S)",
                "description": f"Identificados {len(processos_detalhados)} registros judiciais em fontes públicas",
                "source": "Análise Completa Google",
                "note": "⚠️ Verificar detalhes em portais oficiais: CNJ, Jusbrasil, PJe"
            })
        
        processos.extend(processos_detalhados[:10])
        
        print("  🏢 Analisando vínculos empresariais...")
        
        # 2. EMPRESAS E CNPJS
        empresas = []
        
        cnpj_patterns = [
            r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}',
            r'\d{14}',
        ]
        
        cnpjs_encontrados = []
        for pattern in cnpj_patterns:
            matches = re.findall(pattern, all_text)
            cnpjs_encontrados.extend(matches)
        
        cnpjs_unicos = list(set(cnpjs_encontrados))[:10]
        
        for cnpj in cnpjs_unicos:
            empresas.append({
                "type": "🏢 CNPJ IDENTIFICADO",
                "company": f"Empresa com CNPJ: {cnpj}",
                "cnpj": cnpj,
                "details": "CNPJ encontrado em registro público",
                "source": "Google Search",
                "note": "Consultar na Receita Federal para mais detalhes"
            })
        
        empresa_keywords = ['cnpj', 'empresa', 'sócio', 'mei', 'ltda', 'eireli', 'administrador', 'proprietário', 'dono', 'empresário']
        
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            
            if any(word in text.lower() for word in empresa_keywords):
                
                vinculo = "Vínculo não especificado"
                if 'sócio' in text.lower():
                    vinculo = "Sócio"
                elif 'administrador' in text.lower():
                    vinculo = "Administrador"
                elif 'proprietário' in text.lower() or 'dono' in text.lower():
                    vinculo = "Proprietário"
                elif 'mei' in text.lower():
                    vinculo = "MEI"
                
                empresas.append({
                    "type": f"💼 {vinculo}",
                    "company": result['title'][:150],
                    "details": result['snippet'][:300],
                    "source": "Google Search",
                    "url": result['url']
                })
        
        print("  📱 Analisando redes sociais...")
        
        # 3. REDES SOCIAIS
        social_media = []
        
        linkedin_urls = re.findall(r'linkedin\.com/in/([\w-]+)', all_text)
        for username in set(linkedin_urls[:5]):
            social_media.append({
                "platform": "💼 LinkedIn",
                "profile": username,
                "url": f"https://www.linkedin.com/in/{username}",
                "status": "Perfil público encontrado"
            })
        
        facebook_urls = re.findall(r'facebook\.com/([\w.]+)', all_text)
        for username in set(facebook_urls[:5]):
            if 'pages' not in username and 'groups' not in username and 'watch' not in username:
                social_media.append({
                    "platform": "📘 Facebook",
                    "profile": username,
                    "url": f"https://www.facebook.com/{username}",
                    "status": "Perfil encontrado"
                })
        
        instagram_urls = re.findall(r'instagram\.com/([\w.]+)', all_text)
        for username in set(instagram_urls[:5]):
            if 'explore' not in username and 'p/' not in username:
                social_media.append({
                    "platform": "📷 Instagram",
                    "profile": f"@{username}",
                    "url": f"https://www.instagram.com/{username}",
                    "status": "Perfil público"
                })
        
        twitter_urls = re.findall(r'(?:twitter|x)\.com/([\w]+)', all_text)
        for username in set(twitter_urls[:3]):
            if username not in ['status', 'i', 'search', 'hashtag']:
                social_media.append({
                    "platform": "🐦 Twitter/X",
                    "profile": f"@{username}",
                    "url": f"https://twitter.com/{username}",
                    "status": "Perfil público"
                })
        
        print("  👥 Analisando informações familiares...")
        
        # 4. INFORMAÇÕES FAMILIARES
        family_info = []
        family_keywords = {
            'filho': '👦 Filho',
            'filha': '👧 Filha',
            'pai': '👨 Pai',
            'mãe': '👩 Mãe',
            'mae': '👩 Mãe',
            'esposa': '💑 Esposa',
            'marido': '💑 Marido',
            'irmão': '👬 Irmão',
            'irmao': '👬 Irmão',
            'irmã': '👭 Irmã',
            'irma': '👭 Irmã',
        }
        
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            
            for keyword, tipo in family_keywords.items():
                if keyword in text.lower() and len(text) > 50:
                    family_info.append({
                        "type": tipo,
                        "details": result['snippet'][:250],
                        "source": "Google Search",
                        "note": "⚠️ Verificar manualmente - podem existir homônimos"
                    })
                    
                    if len(family_info) >= 8:
                        break
            
            if len(family_info) >= 8:
                break
        
        print("  📰 Analisando notícias e menções públicas...")
        
        # 5. NOTÍCIAS E MENÇÕES
        public_records = []
        
        for result in all_results[:30]:
            title = result['title']
            snippet = result['snippet']
            url = result['url']
            
            categoria = "📋 Menção Pública"
            
            if any(word in url.lower() for word in ['g1.com', 'uol.com', 'folha', 'estadao', 'globo']):
                categoria = "📰 Notícia"
            elif any(word in snippet.lower() for word in ['atleta', 'esporte', 'campeonato', 'competição']):
                categoria = "🏃 Atividade Esportiva"
            elif any(word in snippet.lower() for word in ['curso', 'palestra', 'evento']):
                categoria = "🎓 Eventos"
            
            public_records.append({
                "source": categoria,
                "title": title[:200],
                "snippet": snippet[:350],
                "url": url
            })
        
        print("  📊 Compilando relatório final...")
        
        stats = {
            "total_resultados_analisados": len(all_results),
            "queries_realizadas": len(queries),
            "processos_encontrados": len(processos),
            "empresas_encontradas": len(empresas),
            "redes_sociais_encontradas": len(social_media),
            "mencoes_familiares": len(family_info),
            "registros_publicos": len(public_records)
        }
        
        print(f"  ✅ BUSCA CONCLUÍDA:")
        print(f"     - {stats['total_resultados_analisados']} resultados analisados")
        print(f"     - {stats['processos_encontrados']} processos identificados")
        print(f"     - {stats['empresas_encontradas']} vínculos empresariais")
        print(f"     - {stats['redes_sociais_encontradas']} perfis sociais")
        
        return {
            "processos": processos,
            "processo_count": processo_count,
            "empresas": empresas,
            "social_media": social_media,
            "public_records": public_records[:30],
            "family_info": family_info,
            "statistics": stats
        }
    
    async def search_person(self, full_name: str) -> Dict[str, Any]:
        """Busca PROFUNDA com 10 queries"""
        
        print(f"🔍 Iniciando busca PROFUNDA por: {full_name}")
        
        extracted_data = await self.extract_info_from_google(full_name)
        
        social_media = extracted_data["social_media"]
        legal_records = extracted_data["processos"]
        professional = extracted_data["empresas"]
        public_records = extracted_data["public_records"]
        family_info = extracted_data["family_info"]
        processo_count = extracted_data["processo_count"]
        
        if not social_media:
            social_media.append({
                "platform": "Busca Geral",
                "profile": f"Nenhum perfil público encontrado para {full_name}",
                "status": "Não encontrado",
                "note": "Recomenda-se busca manual em redes sociais"
            })
        
        if not legal_records:
            legal_records.append({
                "type": "Processos Judiciais",
                "title": "Nenhum processo encontrado em busca pública",
                "source": "Google Search",
                "note": "Verificar manualmente em portais oficiais (CNJ, TJ estaduais)"
            })
        
        if not professional:
            professional.append({
                "type": "Vínculos Empresariais",
                "company": "Nenhum vínculo empresarial encontrado",
                "source": "Google Search",
                "note": "Verificar na Receita Federal e Juntas Comerciais"
            })
        
        if not public_records:
            public_records.append({
                "source": "Google Search",
                "title": "Informações limitadas disponíveis",
                "snippet": "Recomenda-se verificação em fontes oficiais"
            })
        
        if not family_info:
            family_info.append({
                "type": "Informações Familiares",
                "status": "Não disponível em fontes públicas",
                "note": "Informações familiares requerem acesso a registros civis oficiais"
            })
        
        sources_searched = 10
        profiles_found = len(social_media) + len(legal_records) + len(professional)
        
        results = {
            "name": full_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources_searched": sources_searched,
            "profiles_found": profiles_found,
            "social_media": social_media,
            "legal_records": legal_records,
            "professional": professional,
            "family_info": family_info,
            "public_records": public_records,
            "risk_assessment": "baixo" if not legal_records or len(legal_records) == 1 else "médio",
            "disclaimer": "⚠️ IMPORTANTE: Informações coletadas de fontes públicas disponíveis na internet. Este relatório é apenas um ponto de partida. É OBRIGATÓRIO realizar verificação cruzada independente em fontes oficiais antes de tomar qualquer decisão. Podem existir homônimos ou dados desatualizados."
        }
        
        print(f"✅ Busca concluída: {profiles_found} resultados encontrados")
        
        return results

search_system = RealPersonSearch()

# Funções utilitárias
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_jwt_token(user_data: dict) -> str:
    payload = {
        "user_id": user_data["_id"],
        "email": user_data["email"],
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def get_current_user(authorization: Optional[str] = Header(None, alias="Authorization")):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autorização necessário")
    
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

# Rotas da API
@app.post("/api/auth/register")
async def register_user(user_data: UserCreate):
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    user_id = str(uuid.uuid4())
    new_user = {
        "_id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "credits": 0,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.users.insert_one(new_user)
    
    return {
        "message": "Usuário criado com sucesso",
        "user": UserResponse(
            id=user_id,
            email=user_data.email,
            credits=0,
            created_at=new_user["created_at"]
        )
    }

@app.post("/api/auth/login")
async def login_user(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email})
    
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")
    
    token = create_jwt_token(user)
    
    return {
        "token": token,
        "user": UserResponse(
            id=user["_id"],
            email=user["email"],
            credits=user.get("credits", 0),
            created_at=user["created_at"]
        )
    }

@app.post("/api/search")
async def search_person(search_data: SearchRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("credits", 0) < 1:
        raise HTTPException(status_code=400, detail="Créditos insuficientes")
    
    search_results = await search_system.search_person(search_data.name)
    
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$inc": {"credits": -1}}
    )
    
    search_record = {
        "_id": str(uuid.uuid4()),
        "user_email": current_user["email"],
        "search_name": search_data.name,
        "results": search_results,
        "credits_used": 1,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.searches.insert_one(search_record)
    return search_results

@app.post("/api/purchase")
async def create_purchase(purchase_data: PurchaseRequest, current_user: dict = Depends(get_current_user)):
    transaction_id = str(uuid.uuid4())
    transaction = {
        "_id": transaction_id,
        "user_email": current_user["email"],
        "package_type": purchase_data.package_type,
        "amount": purchase_data.amount,
        "credits": purchase_data.credits,
        "status": "pending",
        "payment_method": "mercadopago",
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.transactions.insert_one(transaction)
    
    return {
        "transaction_id": transaction_id,
        "pix_info": {
            "key": PIX_KEY,
            "name": PIX_NAME,
            "amount": purchase_data.amount
        }
    }

@app.get("/api/admin/stats")
async def get_admin_stats():
    total_users = await db.users.count_documents({})
    total_searches = await db.searches.count_documents({})
    confirmed_transactions = await db.transactions.find({"status": "confirmed"}).to_list(None)
    total_revenue = sum(t["amount"] for t in confirmed_transactions)
    
    return {
        "total_users": total_users,
        "total_searches": total_searches,
        "total_revenue": total_revenue,
        "today_sales": 0
    }

@app.get("/api/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["_id"],
        email=current_user["email"],
        credits=current_user.get("credits", 0),
        created_at=current_user["created_at"]
    )

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
    email = data.get("email")
    credits = data.get("credits", 0)
    
    result = await db.users.update_one(
        {"email": email},
        {"$inc": {"credits": int(credits)}}
    )
    
    if result.matched_count > 0:
        return {"success": True, "message": f"{credits} créditos adicionados para {email}"}
    else:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}

@app.get("/")
async def root():
    return {"message": "VerificaPessoa API is running"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
