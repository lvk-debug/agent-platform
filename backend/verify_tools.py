from app.core.database import SessionLocal
from app.models.tool import Tool

db = SessionLocal()
tools = db.query(Tool).filter(Tool.is_active == True).all()
print(f'工具列表 ({len(tools)} 个):')
for t in tools:
    print(f'  - {t.name}: {t.description}')
db.close()
