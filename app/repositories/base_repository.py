from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[List] = None,
        order_by=None,
    ) -> tuple[List[ModelType], int]:
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        if order_by is not None:
            query = query.order_by(order_by)

        total = (await self.db.execute(count_query)).scalar()
        result = await self.db.execute(query.offset(skip).limit(limit))
        items = result.scalars().all()
        return list(items), total

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update(self, instance: ModelType, **kwargs) -> ModelType:
        for key, value in kwargs.items():
            if value is not None or key in kwargs:
                setattr(instance, key, value)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> bool:
        await self.db.delete(instance)
        await self.db.flush()
        return True

    async def count(self, filters: Optional[List] = None) -> int:
        query = select(func.count()).select_from(self.model)
        if filters:
            query = query.where(and_(*filters))
        result = await self.db.execute(query)
        return result.scalar()
