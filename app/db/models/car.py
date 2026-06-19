from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.driver import Driver


class Car(Base):
    __tablename__ = "Car"

    id: Mapped[str] = mapped_column(String(191), primary_key=True)
    driver_id: Mapped[str] = mapped_column(
        "driverId",
        String(191),
        ForeignKey("Driver.id", ondelete="CASCADE"),
        unique=True,
    )
    car_name: Mapped[str] = mapped_column("carName", String(191))
    car_number: Mapped[str] = mapped_column("carNumber", String(191), unique=True)
    capacity: Mapped[int] = mapped_column(Integer)

    driver: Mapped["Driver"] = relationship("Driver", back_populates="car")
