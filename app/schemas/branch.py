from pydantic import BaseModel


class BranchNameResponse(BaseModel):
    id: int
    name: str
    address: str

    class Config:
        from_attributes = True
