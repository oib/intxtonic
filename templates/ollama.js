// ollama.js – OpenAI-kompatibler API-Aufruf für Open-WebUI

export async function checkWithOllama(sequence) {
    const prompt = sequence.join(" ");

    const BASE = process.env.OLLAMA_BASE || process.env.OPENAI_BASE_URL || "https://at1.dynproxy.net";
    const API_KEY = process.env.OLLAMA_API_KEY || process.env.OPENAI_API_KEY || "";
    const MODEL = process.env.OLLAMA_MODEL || "gemma3:1b";

    try {
        const response = await fetch(`${BASE.replace(/\/$/, "")}/api/chat/completions`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(API_KEY ? { "Authorization": `Bearer ${API_KEY}` } : {})
            },
            body: JSON.stringify({
                model: MODEL,
                messages: [
                  {
                    role: "system",
                    content: "You are the SoulTribe Match Annotator. Given compact match details (users, score, and a short breakdown), write a concise, friendly, plain-text comment (1–2 sentences) that explains the compatibility in simple terms. Mention strong points first. If the score is modest, be encouraging. Do not include JSON or additional formatting—just the comment."
                  },
                  { role: "user", content: prompt }
                ],
                stream: false
            })
        });

        if (!response.ok) {
            console.error("Ollama API Error:", response.status);
            return "(Fehler beim LLM-Request)";
        }

        const data = await response.json();
        return data.choices?.[0]?.message?.content?.trim() || "(keine Antwort vom Modell)";

    } catch (error) {
        console.error("LLM-Request fehlgeschlagen:", error);
        return "(Verbindungsfehler mit Ollama)";
    }
}

