import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
import aiohttp
import os

app = FastAPI()
client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

class Topic(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)

class GenerationStatus(BaseModel):
    task_id: str
    status: str
    result: dict = None

generation_tasks = {}

async def get_recent_news(topic: str) -> str:
    async with aiohttp.ClientSession() as session:
        url = f"https://newsapi.org/v2/everything?q={topic}&apiKey=YOUR_NEWS_API_KEY"
        async with session.get(url) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="Failed to fetch news")
            data = await response.json()
            articles = data.get("articles", [])
            recent_news = [article.get("title", "") for article in articles[:3]]
            return "\n".join(recent_news)

async def generate_content(prompt: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        n=1,
        stop=None,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

async def generate_post_async(topic: str, task_id: str):
    try:
        generation_tasks[task_id]['status'] = 'Fetching recent news'
        recent_news = await get_recent_news(topic)

        generation_tasks[task_id]['status'] = 'Generating title'
        title = await generate_content(f"Write a catchy title for a blog post about {topic}")

        generation_tasks[task_id]['status'] = 'Generating meta description'
        meta_description = await generate_content(f"Write a brief meta description for a blog post titled '{title}'")

        generation_tasks[task_id]['status'] = 'Generating post content'
        post_content = await generate_content(f"Write a detailed blog post about {topic}. Consider these recent news:\n{recent_news}")

        generation_tasks[task_id]['status'] = 'Completed'
        generation_tasks[task_id]['result'] = {
            "title": title,
            "meta_description": meta_description,
            "post_content": post_content
        }
    except Exception as e:
        generation_tasks[task_id]['status'] = 'Failed'
        generation_tasks[task_id]['result'] = {"error": str(e)}

@app.post("/generate-post")
async def generate_post(topic: Topic, background_tasks: BackgroundTasks):
    task_id = f"task_{len(generation_tasks) + 1}"
    generation_tasks[task_id] = {'status': 'Initialized'}
    background_tasks.add_task(generate_post_async, topic.topic, task_id)
    return {"task_id": task_id, "message": "Post generation started"}

@app.get("/generation-status/{task_id}")
async def get_generation_status(task_id: str):
    if task_id not in generation_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return GenerationStatus(
        task_id=task_id,
        status=generation_tasks[task_id]['status'],
        result=generation_tasks[task_id].get('result')
    )

@app.post("/heartbeat")
async def heartbeat():
    return {"status": "OK"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
