import os
import random
import argparse
import tempfile
import shutil
import re
from dotenv import load_dotenv
from jinja2 import Template
from git import Repo
import requests
import markdown
from markdown.extensions import tables
from openai import OpenAI

load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

def call_qwen(prompt, model="qwen-plus-2025-04-28"):
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
    )
    return completion.choices[0].message.content

def extract_intro(text):
    import re
    match = re.search(r"## Введение\s*(.*?)\s*##", text, re.DOTALL | re.IGNORECASE)
    if match:
        intro = match.group(1).strip()
        return intro[:500]
    return text[:500]

def generate_article_text(idea):
    prompt = f"""
Сгенерируй полную псевдонаучную статью на тему: "{idea}".

Требования к структуре и оформлению:
- Напиши статью в научном стиле, как для научного журнала.
- Используй разметку Markdown (заголовки **##**, выделения **жирным**, списки и т.д.).
- Статья должна включать следующие разделы в таком порядке:
  1. **Название** 
  2. **Аннотация** — 2–3 предложения
  3. **Дата публикации** (выдуманная, но реалистичная)
  4. **Введение**
  5. **Основная теоретическая часть**
  6. **Методы и эксперименты** (вымышленные)
  7. **Результаты**
  8. **Обсуждение**
  9. **Выводы**
  10. **Источники** (вымышленные, оформленные как научные)

Статья должна выглядеть убедительно, быть логично структурированной, но по сути — абсурдной и сатиричной.

Пример темы: квантовая любовь в инфракрасной материи.

Не пиши явно «Тема:» — просто сразу переходи к структуре статьи.
"""

    return call_qwen(prompt)


def generate_summary_article(idea, generated_articles):
    refs = ""
    for article in generated_articles:
        refs += f"""
Статья: {article['title']}
Ссылка: {article['url']}
Краткое содержание: {article['summary']}
"""

    prompt = f"""
Ты — известный псевдонаучный учёный. На тему "{idea}" было опубликовано несколько важных исследований. Вот их список:

{refs}

На основе этих материалов напиши псевдонаучную **обзорную метастатью**, которая:
- Оформлена как обычная статья (заголовок, аннотация, дата, введение, теория, методы, результаты, выводы, источники)
- Ссылается на упомянутые статьи прямо в тексте
- Использует Markdown-ссылки
- Написана в псевдонаучном научном стиле
"""

    return call_qwen(prompt)

def generate_fake_author():
    prompt = """
Придумай уникальное вымышленное имя и фамилию для автора псевдонаучной статьи.
Имя должно звучать как у академика, но **отличаться от предыдущих**. Используй редкие или необычные сочетания.
Ответь только именем и фамилией, без кавычек и пояснений.
"""
    return call_qwen(prompt)

def generate_review(maintheme):
    prompt = f"""
Напиши научную рецензию на статью под названием: "{maintheme}". Стиль — псевдонаучный, благосклонный, с упоминанием важности работы. Не забудь добавить Имя автора рецензии и его регалии
"""
    return call_qwen(prompt)

def generate_title(text):
    prompt = f"""
Придумай название заголовка в научном журнале для этой научной статьи. Стиль статьи— псевдонаучный, благосклонный, с упоминанием важности работы.
Твой ответ должен содержать одно лишь название заголовка которое ты придумаешь без кавычек или скобок


Название статьи : {text}
"""
    return call_qwen(prompt)


def get_keywords_from_idea(idea):
    prompt = f"""
Extract 2–3 concise English keywords or phrases from the topic below. 
They should be suitable for use in a scientific journal or research lab name.
Avoid punctuation, use only lowercase words with dashes instead of spaces.
Only return the list of keywords, comma-separated.

Topic: "{idea}"
"""
    response = call_qwen(prompt)
    keywords = response.lower().strip().split(",")
    keywords = [re.sub(r'[^a-z0-9\-]', '', kw.strip().replace(" ", "-")) for kw in keywords if kw.strip()]
    return keywords[:3]


def generate_repo_name_from_keywords(keywords):
    prefixes = ["journal", "institute", "center", "lab", "society"]
    prefix = random.choice(prefixes)
    cleaned = [kw for kw in keywords if kw]
    if not cleaned:
        cleaned = ["pseudo", "science"]
    return prefix + "-" + "-".join(cleaned)

def render_article_html(title, author, body, review, template_index=0):
    template_path = f"templates/article_template_{template_index + 1}.html"
    with open(template_path, encoding="utf-8") as f:
        template = Template(f.read())
    body_html = markdown.markdown(body, extensions=['tables'], output_format="html5")
    title_html = markdown.markdown(title, extensions=['tables'], output_format='html5')
    review_html = markdown.markdown(review, extensions=['tables'], output_format="html5")
    return template.render(
        title=title_html,
        author=author,
        body=body_html,
        review=review_html
    )

def extract_maintheme(text):
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    maintheme = lines[0]
    maintheme = re.sub(r"\*+", "", maintheme).strip(":- ")
    return maintheme



def create_github_repo(repo_name, private=False):
    token = GITHUB_TOKEN
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    url = f"https://api.github.com/user/repos"
    data = {
        "name": repo_name,
        "private": private,
        "auto_init": False,
        "gitignore_template": "Python"
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        print(f"Репозиторий {repo_name} создан")
    elif response.status_code == 422:
        print(f"Репозиторий {repo_name} уже существует")
    else:
        raise Exception(f"Ошибка создания репозитория: {response.status_code} {response.text}")

def publish_to_github(repo_name, html_content):
    create_github_repo(repo_name, private=False)

    tmp_dir = tempfile.mkdtemp()
    repo_url = f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{repo_name}.git"
    Repo.clone_from(repo_url, tmp_dir)

    with open(os.path.join(tmp_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    repo = Repo(tmp_dir)
    repo.git.add(all=True)
    repo.index.commit("Add article")
    repo.remote().push()

    shutil.rmtree(tmp_dir)
    print(f"Опубликовано: https://{GITHUB_USERNAME}.github.io/{repo_name}/")

def enable_github_pages(repo_name):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/pages"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    data = {
        "source": {
            "branch": "main",
            "path": "/"
        }
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code in [201, 204]:
        print(f"GitHub Pages включён для {repo_name}")
    else:
        print(f"Не удалось включить GitHub Pages для {repo_name}: {response.status_code} {response.text}")


def main():
    idea = input("Введите тему псевдонаучной статьи: ").strip()
    num_sites = int(input("Сколько сайтов опубликовать? (1–3): ") or "1")
    num_sites = min(max(num_sites, 1), 3)

    generated_articles = []
    num_templates = 4  

    for i in range(num_sites):
        print(f"\nГенерация версии #{i+1}")

        variation_prompt = f"Вариация темы: {idea}. Добавь другой акцент или научный взгляд, сохрани суть."
        varied_idea = call_qwen(variation_prompt)
        print(f"➡ Вариация темы: {varied_idea.strip()}")

        print("Извлекаем ключевые слова...")
        keywords = get_keywords_from_idea(varied_idea)
        print(f"➡ Ключевые слова #{i+1}: {keywords}")

        print("Генерация статьи...")
        article_text = generate_article_text(varied_idea)

        print("Генерация заголовка...")
        title = generate_title(article_text)

        print("Извлечение главной темы...")
        maintheme = extract_maintheme(article_text)

        print("📝 Генерация рецензии...")
        review = generate_review(maintheme)

        print("Генерация имени автора...")
        author = generate_fake_author()
        print(f"➡ Автор: {author}")

        template_index = i % num_templates

        html = render_article_html(title, author, article_text, review, template_index)

        repo_name = generate_repo_name_from_keywords(keywords)
        print(f"Публикация в репозиторий {repo_name}...")
        publish_to_github(repo_name, html)
        enable_github_pages(repo_name)

        summary = extract_intro(article_text)

        generated_articles.append({
            "title": title,
            "url": f"https://{GITHUB_USERNAME}.github.io/{repo_name}/",
            "maintheme": maintheme,
            "summary": summary
        })

    generate_meta = input("\nСгенерировать обзорную метастатью? (y/n): ").strip().lower()
    if generate_meta != "y":
        print("Обзорная метастатья не будет создана.")
        return

    print("\nГенерация обзорной статьи...")
    summary_article_md = generate_summary_article(idea, generated_articles)
    summary_title = generate_title(summary_article_md)
    summary_author = generate_fake_author()
    summary_review = generate_review(summary_title)
    summary_html = render_article_html(summary_title, summary_author, summary_article_md, summary_review, template_index=3)  # Для метастатьи можно первый шаблон
    summary_keywords = get_keywords_from_idea(idea)
    summary_repo_name = generate_repo_name_from_keywords(summary_keywords)
    print(f"Публикация в репозиторий {summary_repo_name}...")
    publish_to_github(summary_repo_name, summary_html)
    enable_github_pages(summary_repo_name)

if __name__ == "__main__":
    main()
