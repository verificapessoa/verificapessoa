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
from urllib.parse import quote, unquote
from dotenv import load_dotenv
from pathlib import Path
import re
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'verificapessoa')
JWT_SECRET = os.environ.get('JWT_SECRET', 'verificapessoa_secret_2025')
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
    name: Optional[str] = None
    cpf: Optional[str] = None
    
class PurchaseRequest(BaseModel):
    package_type: str
    amount: float
    credits: int

# SISTEMA MULTI-SEARCH (Google + Bing + DuckDuckGo)
class MultiSearchEngine:
    def __init__(self):
        self.timeout = 30
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
    
    def get_headers(self):
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    async def search_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        """DuckDuckGo - HTML simples sem JavaScript"""
        try:
            print(f"    🦆 Buscando no DuckDuckGo: {query[:50]}...")
            
            encoded_query = quote(query)
            url = f'https://html.duckduckgo.com/html/?q={encoded_query}'
            
            headers = self.get_headers()
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                print(f"    ❌ DuckDuckGo status {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # DuckDuckGo tem estrutura simples
            result_divs = soup.find_all('div', class_='result')
            
            for div in result_divs[:20]:
                title_elem = div.find('a', class_='result__a')
                snippet_elem = div.find('a', class_='result__snippet')
                
                if title_elem:
                    title = title_elem.get_text().strip()
                    snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                    url = title_elem.get('href', '')
                    
                    results.append({
                        "engine": "DuckDuckGo",
                        "title": title[:300],
                        "snippet": snippet[:500],
                        "url": url[:500]
                    })
            
            print(f"    ✅ DuckDuckGo: {len(results)} resultados")
            return results
            
        except Exception as e:
            print(f"    ❌ Erro DuckDuckGo: {str(e)[:100]}")
            return []
    
    async def search_bing(self, query: str) -> List[Dict[str, Any]]:
        """Bing - Alternativa ao Google"""
        try:
            print(f"    🔵 Buscando no Bing: {query[:50]}...")
            
            encoded_query = quote(query)
            url = f'https://www.bing.com/search?q={encoded_query}&count=30&setlang=pt-BR'
            
            headers = self.get_headers()
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                print(f"    ❌ Bing status {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Bing usa class 'b_algo'
            result_divs = soup.find_all('li', class_='b_algo')
            
            for div in result_divs[:20]:
                title_elem = div.find('h2')
                snippet_elem = div.find('p') or div.find('div', class_='b_caption')
                link_elem = div.find('a', href=True)
                
                if title_elem:
                    title = title_elem.get_text().strip()
                    snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                    url = link_elem['href'] if link_elem else ""
                    
                    results.append({
                        "engine": "Bing",
                        "title": title[:300],
                        "snippet": snippet[:500],
                        "url": url[:500]
                    })
            
            print(f"    ✅ Bing: {len(results)} resultados")
            return results
            
        except Exception as e:
            print(f"    ❌ Erro Bing: {str(e)[:100]}")
            return []
    
    async def search_google(self, query: str) -> List[Dict[str, Any]]:
        """Google - Tentativa com múltiplos seletores"""
        try:
            print(f"    🔴 Buscando no Google: {query[:50]}...")
            
            encoded_query = quote(query)
            url = f'https://www.google.com/search?q={encoded_query}&num=30&hl=pt-BR'
            
            headers = self.get_headers()
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                print(f"    ❌ Google status {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Múltiplos seletores do Google
            search_divs = (
                soup.find_all('div', class_='g') or
                soup.find_all('div', class_='tF2Cxc') or
                soup.select('div[data-hveid]')
            )
            
            for div in search_divs[:20]:
                title_elem = div.find('h3')
                snippet_elem = div.find('div', class_='VwiC3b') or div.find('span')
                link_elem = div.find('a', href=True)
                
                if title_elem:
                    title = title_elem.get_text().strip()
                    snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                    url = link_elem['href'] if link_elem else ""
                    
                    if url.startswith('/url?q='):
                        url = url.split('/url?q=')[1].split('&')[0]
                    
                    results.append({
                        "engine": "Google",
                        "title": title[:300],
                        "snippet": snippet[:500],
                        "url": url[:500]
                    })
            
            print(f"    ✅ Google: {len(results)} resultados")
            return results
            
        except Exception as e:
            print(f"    ❌ Erro Google: {str(e)[:100]}")
            return []
    
    async def search_multi_engine(self, query: str) -> List[Dict[str, Any]]:
        """Busca em TODOS os motores e combina resultados"""
        
        all_results = []
        
        # ESTRATÉGIA: Tentar todos em paralelo
        print(f"\n  🔍 Buscando '{query}' em 3 motores...")
        
        # DuckDuckGo (mais confiável)
        duckduckgo_results = await self.search_duckduckgo(query)
        all_results.extend(duckduckgo_results)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        # Bing (backup)
        bing_results = await self.search_bing(query)
        all_results.extend(bing_results)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        # Google (se os outros falharem)
        if len(all_results) < 5:
            google_results = await self.search_google(query)
            all_results.extend(google_results)
        
        print(f"  ✅ Total: {len(all_results)} resultados de múltiplas fontes")
        
        return all_results
    
    async def extract_info_multi_engine(self, name: str) -> Dict[str, Any]:
        """BUSCA com múltiplos motores (DuckDuckGo, Bing, Google)"""
        
        print(f"\n{'='*80}")
        print(f"🔍 BUSCA MULTI-ENGINE: {name}")
        print(f"{'='*80}\n")
        
        queries = [
            f'"{name}"',
            f'"{name}" Brasil',
            f'"{name}" processos judiciais',
            f'"{name}" CNPJ empresa',
            f'"{name}" LinkedIn',
            f'"{name}" redes sociais',
        ]
        
        all_results = []
        all_text = ""
        
        for i, query in enumerate(queries):
            print(f"\n📊 Query {i+1}/{len(queries)}: {query}")
            
            results = await self.search_multi_engine(query)
            
            if results:
                all_results.extend(results)
                for r in results:
                    all_text += " " + r['title'].lower() + " " + r['snippet'].lower()
                print(f"  ✅ Total acumulado: {len(all_results)} resultados")
            else:
                print(f"  ⚠️ Query sem resultados")
        
        print(f"\n{'='*80}")
        print(f"📊 TOTAL: {len(all_results)} resultados")
        print(f"{'='*80}\n")
        
        # ANÁLISE
        
        print("⚖️ Analisando processos...")
        processos = []
        processo_count = 0
        
        processo_patterns = [r'(\d+)\s*processo[s]?', r'(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})']
        
        for pattern in processo_patterns:
            matches = re.findall(pattern, all_text)
            for match in matches:
                if isinstance(match, str) and match.isdigit():
                    num = int(match)
                    if 0 < num < 1000 and num > processo_count:
                        processo_count = num
        
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            if any(word in text.lower() for word in ['processo', 'tribunal', 'juiz', 'ação', 'sentença']):
                processos.append({
                    "type": "Processo Judicial",
                    "title": result['title'][:250],
                    "description": result['snippet'][:400],
                    "source": result['engine'],
                    "url": result['url']
                })
        
        if processo_count > 0:
            processos.insert(0, {
                "type": "📊 RESUMO",
                "title": f"⚖️ {processo_count} PROCESSO(S) IDENTIFICADO(S)",
                "description": f"Total: {len(processos)} registros encontrados",
                "source": "Análise Multi-Engine"
            })
        
        print(f"✅ {len(processos)} processos")
        
        print("🏢 Analisando empresas...")
        empresas = []
        
        cnpj_pattern = r'\d{2}\.?\d{3}\.?\d{3}[/]?\d{4}[-]?\d{2}'
        cnpjs = re.findall(cnpj_pattern, all_text)
        
        for cnpj in list(set(cnpjs))[:10]:
            empresas.append({
                "type": "🏢 CNPJ",
                "company": f"CNPJ: {cnpj}",
                "cnpj": cnpj,
                "source": "Multi-Engine"
            })
        
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            if any(word in text.lower() for word in ['cnpj', 'empresa', 'sócio', 'mei', 'ltda']):
                empresas.append({
                    "type": "💼 Vínculo Empresarial",
                    "company": result['title'][:200],
                    "details": result['snippet'][:300],
                    "source": result['engine'],
                    "url": result['url']
                })
        
        print(f"✅ {len(empresas)} empresas")
        
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
        
        print(f"✅ {len(social_media)} perfis")
        
        print("👥 Analisando família...")
        family_info = []
        family_keywords = {'filho': '👦 Filho', 'filha': '👧 Filha', 'pai': '👨 Pai', 'mãe': '👩 Mãe', 'esposa': '💑 Esposa', 'irmão': '👬 Irmão', 'irmã': '👭 Irmã'}
        
        for result in all_results:
            text = result['title'] + " " + result['snippet']
            for keyword, tipo in family_keywords.items():
                if keyword in text.lower():
                    family_info.append({
                        "type": tipo,
                        "details": result['snippet'][:250],
                        "source": result['engine']
                    })
                    if len(family_info) >= 8: break
            if len(family_info) >= 8: break
        
        print(f"✅ {len(family_info)} menções familiares")
        
        print("📰 Outras informações...")
        public_records = []
        
        for result in all_results[:30]:
            categoria = "📋 Menção"
            if any(w in result['url'].lower() for w in ['g1.com', 'uol.com', 'folha', 'estadao', 'globo']):
                categoria = "📰 Notícia"
            elif any(w in result['snippet'].lower() for w in ['atleta', 'esporte', 'competição', 'campeonato']):
                categoria = "🏃 Esporte"
            
            public_records.append({
                "source": categoria,
                "title": result['title'][:200],
                "snippet": result['snippet'][:350],
                "url": result['url'],
                "engine": result['engine']
            })
        
        print(f"✅ {len(public_records)} registros")
        
        return {
            "processos": processos,
            "processo_count": processo_count,
            "empresas": empresas,
            "social_media": social_media,
            "public_records": public_records,
            "family_info": family_info,
            "total_results": len(all_results)
        }
    
    async def search_person(self, name: Optional[str] = None, cpf: Optional[str] = None) -> Dict[str, Any]:
        """Busca principal - Nome ou CPF"""
        
        if not name and not cpf:
            raise ValueError("Informe nome ou CPF")
        
        # Se tiver CPF, buscar por CPF (mais preciso)
        if cpf:
            print(f"🔍 Busca por CPF: {cpf}")
            search_term = cpf
        else:
            print(f"🔍 Busca por Nome: {name}")
            search_term = name
        
        extracted = await self.extract_info_multi_engine(search_term)
        
        full_name = name or f"CPF {cpf}"
        
        return {
            "name": full_name,
            "cpf": cpf,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources_searched": 3,
            "profiles_found": extracted["total_results"],
            "social_media": extracted["social_media"] if extracted["social_media"] else [{"platform": "Não encontrado", "profile": "Nenhum perfil", "status": "Não encontrado"}],
            "legal_records": extracted["processos"] if extracted["processos"] else [{"type": "Processos", "title": "Nenhum processo encontrado", "source": "Busca Multi-Engine"}],
            "professional": extracted["empresas"] if extracted["empresas"] else [{"type": "Empresas", "company": "Nenhum vínculo encontrado", "source": "Busca Multi-Engine"}],
            "family_info": extracted["family_info"] if extracted["family_info"] else [{"type": "Família", "details": "Não disponível", "note": "Requer registros civis"}],
            "public_records": extracted["public_records"] if extracted["public_records"] else [{"source": "Busca", "title": "Informações limitadas", "snippet": "Verificar outras fontes"}],
            "risk_assessment": "baixo",
            "disclaimer": "⚠️ IMPORTANTE: Informações de fontes públicas. Verificação cruzada obrigatória."
        }

search_system = MultiSearchEngine()

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
    
    # Aceitar nome OU cpf
    results = await search_system.search_person(name=search_data.name, cpf=search_data.cpf)
    
    await db.users.update_one({"_id": current_user["_id"]}, {"$inc": {"credits": -1}})
    await db.searches.insert_one({
        "_id": str(uuid.uuid4()), 
        "user_email": current_user["email"], 
        "search_name": search_data.name or search_data.cpf, 
        "results": results, 
        "created_at": datetime.now(timezone.utc)
    })
    
    return results

@app.post("/api/purchase")
async def create_purchase(purchase_data: PurchaseRequest, current_user: dict = Depends(get_current_user)):
    transaction_id = str(uuid.uuid4())
    await db.transactions.insert_one({
        "_id": transaction_id, 
        "user_email": current_user["email"], 
        "package_type": purchase_data.package_type, 
        "amount": purchase_data.amount, 
        "credits": purchase_data.credits, 
        "status": "pending", 
        "created_at": datetime.now(timezone.utc)
    })
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
    return {"message": "VerificaPessoa API running"}

@app.get("/api/debug/test-engines")
async def test_all_engines():
    """Testa os 3 motores de busca"""
    test_query = "Silas André Bazzilli Caliari"
    
    results = {
        "query": test_query,
        "engines": {}
    }
    
    # Testar DuckDuckGo
    try:
        url_duck = f'https://html.duckduckgo.com/html/?q={quote(test_query)}'
        resp_duck = requests.get(url_duck, timeout=10)
        soup_duck = BeautifulSoup(resp_duck.text, 'html.parser')
        divs_duck = soup_duck.find_all('div', class_='result')
        
        results["engines"]["duckduckgo"] = {
            "status": resp_duck.status_code,
            "html_length": len(resp_duck.text),
            "results_found": len(divs_duck),
            "working": len(divs_duck) > 0
        }
    except Exception as e:
        results["engines"]["duckduckgo"] = {"error": str(e)}
    
    # Testar Bing
    try:
        url_bing = f'https://www.bing.com/search?q={quote(test_query)}&count=10'
        resp_bing = requests.get(url_bing, timeout=10)
        soup_bing = BeautifulSoup(resp_bing.text, 'html.parser')
        divs_bing = soup_bing.find_all('li', class_='b_algo')
        
        results["engines"]["bing"] = {
            "status": resp_bing.status_code,
            "html_length": len(resp_bing.text),
            "results_found": len(divs_bing),
            "working": len(divs_bing) > 0
        }
    except Exception as e:
        results["engines"]["bing"] = {"error": str(e)}
    
    # Testar Google
    try:
        url_google = f'https://www.google.com/search?q={quote(test_query)}&num=10'
        resp_google = requests.get(url_google, timeout=10)
        soup_google = BeautifulSoup(resp_google.text, 'html.parser')
        divs_google = soup_google.find_all('div', class_='g')
        
        results["engines"]["google"] = {
            "status": resp_google.status_code,
            "html_length": len(resp_google.text),
            "results_found": len(divs_google),
            "working": len(divs_google) > 0
        }
    except Exception as e:
        results["engines"]["google"] = {"error": str(e)}
    
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))

