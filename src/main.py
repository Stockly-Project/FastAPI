from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from src.user import routes as user_routes
from src.stock import routes as stock_routes
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .stock.websocket import run_websocket_background_multiple, run_websocket_background_multiple_mock
from .stock.price_websocket import run_asking_websocket_background_multiple, run_asking_websocket_background_multiple_mock
from .logger import logger
from .common.admin_kafka_client import create_kafka_topic
from .stock.crud import get_symbols_for_page
import asyncio

# Kafka 토픽 초기화 함수
async def initialize_kafka():
    # Kafka 토픽을 초기화하는 함수 호출 (토픽이 없다면 생성)
    create_kafka_topic("real_time_stock_prices", num_partitions=1)
    create_kafka_topic("real_time_asking_prices", num_partitions=1)
    logger.info("Kafka topic initialized.")
    

async def schedule_websockets():
    symbol_list = [{"symbol": symbol} for symbol in get_symbols_for_page(1)]
    logger.error(symbol_list)
    try:
        logger.debug("Starting WebSocket tasks...")
        await asyncio.gather(
            run_websocket_background_multiple_mock(symbol_list),
            run_asking_websocket_background_multiple_mock(symbol_list),
        )
        logger.debug("Both WebSocket tasks completed successfully.")
    except Exception as e:
        logger.error(f"Error in WebSocket scheduling task: {e}")


# lifespan 핸들러 설정
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kafka 토픽 초기화가 완료될 때까지 대기
    await initialize_kafka()

    await schedule_websockets()
    logger.info("WebSocket scheduling task executed at app startup.")

    # 필요 시 스케줄러를 추가로 사용할 경우
    scheduler = AsyncIOScheduler()
    # scheduler.add_job(schedule_mock_websockets(), CronTrigger(hour=10, minute=0))  # 매일 오전 10시 실행
    scheduler.add_job(schedule_websockets, CronTrigger(minute="*/10"))  # 테스트용 매 분 스케줄링
    scheduler.start()

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler and WebSocket connections are shut down.")

        
app = FastAPI(lifespan=lifespan)
# app = FastAPI()
router = APIRouter(prefix="/api/v1")
app.include_router(user_routes.router)
app.include_router(stock_routes.router)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def hello():
    return {"message": "메인페이지입니다"}
