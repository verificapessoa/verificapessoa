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
            tlsAllowInvalidCertificates=True  # Para ambientes de produção com certificados auto-assinados
        )
        # Testar conexão
        await client.admin.command('ping')
        db = client[DB_NAME]
        print(f"✅ MongoDB conectado: {DB_NAME}")
    except Exception as e:
        print(f"❌ ERRO ao conectar MongoDB: {e}")
        print(f"❌ MONGO_URL: {MONGO_URL[:50]}...")  # Mostrar parte da URL (sem senha)
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

# Sistema de Busca Real com Web Scraping
class RealPersonSearch:
    def __init__(self):
        self.timeout = 30
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/'
        }
        
    async def search_google(self, name: str) -> List[Dict[str, Any]]:
        """Busca informações gerais no Google"""
        try:
            query = quote(f'"{name}" Brasil')
            url = f'https://www.google.com/search?q={query}&num=10'
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            # Procurar por menções em resultados
            for result in soup.find_all('div', class_='g')[:5]:
                title_elem = result.find('h3')
                snippet_elem = result.find('div', class_='VwiC3b')
                
                if title_elem and snippet_elem:
                    results.append({
                        "source": "Google Search",
                        "title": title_elem.get_text(),
                        "snippet": snippet_elem.get_text()[:200]
                    })
            
            return results
        except Exception as e:
            print(f"Erro Google Search: {e}")
            return []
    
    async def search_jusbrasil(self, name: str) -> List[Dict[str, Any]]:
        """Busca processos judiciais no Jusbrasil"""
        try:
            query = quote(name)
            url = f'https://www.jusbrasil.com.br/busca?q={query}'
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            processes = []
            # Procurar por processos
            for item in soup.find_all('article')[:5]:
                title = item.find('h3') or item.find('h2')
                desc = item.find('p')
                
                if title:
                    processes.append({
                        "type": "Processo Judicial",
                        "title": title.get_text().strip()[:150],
                        "description": desc.get_text().strip()[:200] if desc else "Detalhes não disponíveis",
                        "source": "Jusbrasil"
                    })
            
            return processes
        except Exception as e:
            print(f"Erro Jusbrasil: {e}")
            return []
    
    async def search_linkedin(self, name: str) -> List[Dict[str, Any]]:
        """Busca perfis no LinkedIn"""
        try:
            query = quote(f'{name} site:linkedin.com/in/')
            url = f'https://www.google.com/search?q={query}'
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            profiles = []
            for result in soup.find_all('div', class_='g')[:3]:
                title = result.find('h3')
                link = result.find('a')
                
                if title and link and 'linkedin.com' in link.get('href', ''):
                    profiles.append({
                        "platform": "LinkedIn",
                        "profile": title.get_text(),
                        "url": link.get('href'),
                        "status": "Perfil público encontrado"
                    })
            
            return profiles
        except Exception as e:
            print(f"Erro LinkedIn: {e}")
            return []
    
    async def search_facebook(self, name: str) -> List[Dict[str, Any]]:
        """Busca perfis no Facebook"""
        try:
            query = quote(f'{name} site:facebook.com')
            url = f'https://www.google.com/search?q={query}'
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            profiles = []
            for result in soup.find_all('div', class_='g')[:3]:
                title = result.find('h3')
                link = result.find('a')
                
                if title and link and 'facebook.com' in link.get('href', ''):
                    profiles.append({
                        "platform": "Facebook",
                        "profile": title.get_text(),
                        "url": link.get('href'),
                        "status": "Perfil público encontrado"
                    })
            
            return profiles
        except Exception as e:
            print(f"Erro Facebook: {e}")
            return []
    
    async def search_empresas(self, name: str) -> List[Dict[str, Any]]:
        """Busca vínculos empresariais"""
        try:
            query = quote(f'{name} CNPJ empresa sócio')
            url = f'https://www.google.com/search?q={query}'
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            empresas = []
            for result in soup.find_all('div', class_='g')[:5]:
                title = result.find('h3')
                snippet = result.find('div', class_='VwiC3b')
                
                if title and snippet:
                    text = snippet.get_text()
                    if any(word in text.lower() for word in ['cnpj', 'empresa', 'sócio', 'administrador']):
                        empresas.append({
                            "type": "Vínculo Empresarial",
                            "company": title.get_text()[:100],
                            "details": text[:200],
                            "source": "Registro Público"
                        })
            
            return empresas
        except Exception as e:
            print(f"Erro busca empresas: {e}")
            return []
    
    async def search_person(self, full_name: str) -> Dict[str, Any]:
        """Busca real agregando informações de múltiplas fontes públicas"""
        
        print(f"🔍 Iniciando busca REAL por: {full_name}")
        
        # Executar buscas em paralelo
        google_results = await self.search_google(full_name)
        await asyncio.sleep(1)  # Delay para não sobrecarregar
        
        processos = await self.search_jusbrasil(full_name)
        await asyncio.sleep(1)
        
        linkedin = await self.search_linkedin(full_name)
        await asyncio.sleep(1)
        
        facebook = await self.search_facebook(full_name)
        await asyncio.sleep(1)
        
        empresas = await self.search_empresas(full_name)
        
        # Montar redes sociais
        social_media = []
        social_media.extend(linkedin)
        social_media.extend(facebook)
        
        # Se não encontrou nada específico, adicionar resultado genérico
        if not social_media:
            social_media.append({
                "platform": "Busca Geral",
                "profile": f"Nenhum perfil público encontrado para {full_name}",
                "status": "Não encontrado",
                "note": "Recomenda-se busca manual em redes sociais"
            })
        
        # Processos judiciais
        legal_records = processos if processos else [{
            "type": "Processos Judiciais",
            "title": "Nenhum processo encontrado em busca pública",
            "source": "Jusbrasil",
            "note": "Verificar manualmente em portais oficiais (CNJ, TJ estaduais)"
        }]
        
        # Vínculos empresariais
        professional = empresas if empresas else [{
            "type": "Vínculos Empresariais",
            "company": "Nenhum vínculo empresarial encontrado",
            "source": "Busca Pública",
            "note": "Verificar na Receita Federal e Juntas Comerciais"
        }]
        
        # Informações gerais
        public_records = google_results if google_results else [{
            "source": "Busca Geral",
            "title": "Informações limitadas disponíveis",
            "snippet": "Recomenda-se verificação em fontes oficiais"
        }]
        
        # Familiares (complexo de obter via scraping público)
        family_info = [{
            "type": "Informações Familiares",
            "status": "Não disponível em fontes públicas",
            "note": "Informações familiares requerem acesso a registros civis oficiais"
        }]
        
        sources_searched = 5
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
            "risk_assessment": "baixo" if not processos else "médio",
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

# ROTAS ADMIN 
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
