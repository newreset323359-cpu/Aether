"""Authentication helpers. Passwords use salted PBKDF2-HMAC-SHA256; JWT uses HS256."""
import os,base64,hashlib,hmac,json,time

def _b64(data:bytes)->str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
def _unb64(value:str)->bytes:
    return base64.urlsafe_b64decode(value+"="*((4-len(value)%4)%4))

def hash_password(password:str)->str:
    if len(password)<12: raise ValueError("Password must contain at least 12 characters")
    salt=os.urandom(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,310000)
    return "pbkdf2_sha256$310000$"+_b64(salt)+"$"+_b64(digest)

def verify_password(password:str,encoded:str)->bool:
    try:
        scheme,iterations,salt,digest=encoded.split("$")
        if scheme!="pbkdf2_sha256": return False
        got=hashlib.pbkdf2_hmac("sha256",password.encode(),_unb64(salt),int(iterations))
        return hmac.compare_digest(got,_unb64(digest))
    except Exception:return False

def create_access_token(user_id:int,username:str,is_admin:bool,minutes:int=60):
    secret=os.getenv("AETHER_JWT_SECRET")
    if not secret or len(secret)<32: raise RuntimeError("AETHER_JWT_SECRET must be configured with at least 32 characters")
    now=int(time.time())
    header=_b64(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")).encode())
    payload=_b64(json.dumps({"sub":str(user_id),"username":username,"admin":bool(is_admin),"iat":now,"exp":now+minutes*60},separators=(",",":")).encode())
    body=header+"."+payload
    signature=_b64(hmac.new(secret.encode(),body.encode(),hashlib.sha256).digest())
    return body+"."+signature

def decode_access_token(token:str):
    secret=os.getenv("AETHER_JWT_SECRET")
    if not secret or len(secret)<32: raise ValueError("JWT secret is not configured")
    parts=token.split(".")
    if len(parts)!=3: raise ValueError("Malformed token")
    header=json.loads(_unb64(parts[0]))
    if header.get("alg")!="HS256": raise ValueError("Unsupported token algorithm")
    body=parts[0]+"."+parts[1]
    expected=_b64(hmac.new(secret.encode(),body.encode(),hashlib.sha256).digest())
    if not hmac.compare_digest(expected,parts[2]): raise ValueError("Invalid token signature")
    claims=json.loads(_unb64(parts[1]))
    if int(claims.get("exp",0))<=int(time.time()): raise ValueError("Token expired")
    return claims
