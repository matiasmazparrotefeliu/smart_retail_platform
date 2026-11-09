from pydantic import BaseModel, ConfigDict, EmailStr

class UserRegister(BaseModel):
  company_name: str
  email: EmailStr
  password: str

class UserLogin(BaseModel):
  email: EmailStr
  password: str

class VerifyAccount(BaseModel):
  """Body del endpoint de verificación de cuenta por correo."""
  token: str

class Token(BaseModel):
  access_token: str
  token_type: str

class UserResponse(BaseModel):
  id: int
  email: str
  is_active: bool
  is_verified: bool

  model_config = ConfigDict(from_attributes=True)