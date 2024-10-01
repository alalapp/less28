import os
import re
from fastapi import FastAPI, HTTPException
from openai import OpenAI
import requests
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Инициализация клиента OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def escape_special_characters(text):
    """
    Экранирует специальные символы в тексте.
    """
    escape_dict = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
        '%': '%%',
    }
    return re.sub('|'.join(map(re.escape, escape_dict.keys())),
                  lambda m: escape_dict[m.group()],
                  text)

def get_recent_news(topic):
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey=46bc7c4d105847e6a61ee7e56fdee7fa"
    response = requests.get(url)
    articles = response.json()["articles"]
    recent_news = [escape_special_characters(article["title"]) for article in articles[:3]]
    return "\n".join(recent_news)

def generate_post(topic):
    try:
        recent_news = get_recent_news(topic)

        prompt_title = f"Придумайте привлекательный заголовок для поста на тему: {escape_special_characters(topic)}"
        response_title = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_title}],
            max_tokens=50,
            n=1,
            stop=None,
            temperature=0.7,
        )
        title = escape_special_characters(response_title.choices[0].message.content.strip())

        prompt_meta = f"Напишите краткое, но информативное мета-описание для поста с заголовком: {title}"
        response_meta = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_meta}],
            max_tokens=100,
            n=1,
            stop=None,
            temperature=0.7,
        )
        meta_description = escape_special_characters(response_meta.choices[0].message.content.strip())

        prompt_post = f"Напишите подробный и увлекательный пост для блога на тему: {escape_special_characters(topic)}, учитывая следующие последние новости:\n{recent_news}\n\nИспользуйте короткие абзацы, подзаголовки, примеры и ключевые слова для лучшего восприятия и SEO-оптимизации."
        response_post = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt_post}],
            max_tokens=2048,
            n=1,
            stop=None,
            temperature=0.7,
        )
        post_content = escape_special_characters(response_post.choices[0].message.content.strip())

        return {
            "title": title,
            "meta_description": meta_description,
            "post_content": post_content
        }
    except Exception as e:
        logger.error(f"Error in generate_post: {str(e)}")
        raise

@app.post("/generate-post")
@app.post("/generate-post/")
async def generate_post_api(topic: str):
    try:
        logger.debug(f"Received topic: {topic}")

        if not topic.strip():
            raise HTTPException(status_code=422, detail="Topic cannot be empty")

        generated_post = generate_post(topic)
        return generated_post
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/heartbeat")
async def heartbeat_api():
    return "OK"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
