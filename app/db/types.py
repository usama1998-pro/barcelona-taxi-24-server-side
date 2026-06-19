from sqlalchemy.dialects.mysql import DATETIME

# Prisma uses MySQL DATETIME(3) for millisecond precision.
DatetimeMs = DATETIME(fsp=3)
