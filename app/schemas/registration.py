from pydantic import BaseModel
from .company import CompanyCreate
from .user import AdminUserCreate


class CompanyRegistrationRequest(BaseModel):
    company: CompanyCreate
    admin_user: AdminUserCreate
