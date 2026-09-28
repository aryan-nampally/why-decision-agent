# Publishing checklist

Never name the event, or use its name as a hashtag, in any title, body or comment: posts that do are disqualified. Everything must be public and in English.

## 1. Video (YouTube, public)

- Script: `content/video_script.md` (about 3 minutes; the guide allows 2–5).
- Before recording: `python -m scripts.seed`, start `uvicorn src.app:app --port 8000`, open http://localhost:8000, zoom 110–125%, close notifications. Record at 1080p (OBS). One practice run first.
- Talking head plus screen is preferred: a small webcam corner in OBS is enough.
- Thumbnail: the Nano Banana prompt at the bottom of the script, with your photo attached.
- Title: pick one from the script's title ideas.
- Description: the repo link https://github.com/aryan-nampally/why-decision-agent and https://github.com/vectorize-io/hindsight

## 2. Article (Medium, Dev.to, Hashnode, Substack or LinkedIn Article)

- Source: `article.md` (about 1,450 words; the guide allows 800–1,500). Title is its first line.
- Upload the two images from `docs/img/` (`agent.png`, `health.png`) where the article references them; image paths from the repo won't load on the platform.
- Check the three Hindsight links render as links: GitHub, docs, and the "What is agent memory?" page.
- Optionally embed the YouTube video under the first screenshot.

## 3. Reddit (Link post)

- Post the article URL as a **Link** post to one of: r/llmdevs, r/sideproject, r/aiagents, r/aimemory.
- Title: the article title.

## 4. LinkedIn post (not an article)

- Text: `content/linkedin.md` (750 characters; the limit is 800). The repo link is already in the post.
- Attach a screenshot or the video.
- First comment: the article URL.
- Second comment: `Here's a link to Hindsight if you want to check it out: https://github.com/vectorize-io/hindsight`

## 5. Submission form

- GitHub repo: https://github.com/aryan-nampally/why-decision-agent
- Demo video: the YouTube URL
- Hindsight explanation: https://github.com/aryan-nampally/why-decision-agent/blob/main/HINDSIGHT.md
- Article URL, LinkedIn post URL, Reddit post URL

## 6. Live demo to judges

Same setup as the video. The five-minute path: Postgres question (verdict + no-memory contrast), retry question → Ingest PM-2024-11 → ask again, Record a change, then the Evaluation tab's per-question grid. "Reset demo memory" (bottom of the memory panel, click twice) restores the starting state in about 40 s.
