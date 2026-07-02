import asyncio
from database import connect_to_mongo
from pipeline_runner import resume_pipeline
async def main():
    await connect_to_mongo()
    await resume_pipeline('9423d506-5166-41c6-bab1-bb184a141e32')
asyncio.run(main())
