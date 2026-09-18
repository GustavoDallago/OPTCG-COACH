/**
 * OPTCG Coach - Cloudflare Worker Proxy
 * Protege sua chave GEMINI_API_KEY dos usuarios do frontend,
 * permitindo que qualquer pessoa converse com o Coach IA sem precisar de chave.
 */

export default {
    async fetch(request, env) {
        const corsHeaders = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        };

        // Trata requisicao preflight do navegador (CORS)
        if (request.method === "OPTIONS") {
            return new Response(null, { headers: corsHeaders });
        }

        if (request.method !== "POST") {
            return new Response(JSON.stringify({ error: "Metodo nao permitido" }), {
                status: 405,
                headers: { ...corsHeaders, "Content-Type": "application/json" }
            });
        }

        const apiKey = env.GEMINI_API_KEY;
        if (!apiKey) {
            return new Response(JSON.stringify({ 
                error: { message: "GEMINI_API_KEY nao configurada nas variaveis de ambiente do Cloudflare Worker." } 
            }), {
                status: 500,
                headers: { ...corsHeaders, "Content-Type": "application/json" }
            });
        }

        try {
            const body = await request.json();
            const { systemInstruction, contents, generationConfig } = body;

            if (!contents || !Array.isArray(contents)) {
                return new Response(JSON.stringify({ error: { message: "Parametro contents invalido." } }), {
                    status: 400,
                    headers: { ...corsHeaders, "Content-Type": "application/json" }
                });
            }

            const payload = {
                systemInstruction,
                contents,
                generationConfig: generationConfig || {
                    temperature: 0.7,
                    maxOutputTokens: 2000
                }
            };

            const candidateTargets = [
                { ver: "v1beta", model: "gemini-2.5-flash" },
                { ver: "v1beta", model: "gemini-2.5-flash-lite" },
                { ver: "v1beta", model: "gemini-3.5-flash" },
                { ver: "v1beta", model: "gemini-3.1-flash-lite" },
                { ver: "v1beta", model: "gemini-2.0-flash" },
                { ver: "v1beta", model: "gemini-3.8-flash" }
            ];

            let geminiRes;
            for (const target of candidateTargets) {
                try {
                    geminiRes = await fetch(
                        `https://generativelanguage.googleapis.com/${target.ver}/models/${target.model}:generateContent?key=${encodeURIComponent(apiKey)}`,
                        {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(payload)
                        }
                    );
                    if (geminiRes.ok) break;
                    if (geminiRes.status === 503 || geminiRes.status === 504 || geminiRes.status === 502) {
                        // Modelo temporariamente sobrecarregado; tenta o próximo imediatamente
                        continue;
                    }
                    if (geminiRes.status === 400 || geminiRes.status === 403 || geminiRes.status === 429) {
                        const errJson = await geminiRes.clone().json().catch(() => ({}));
                        const errMsg = errJson.error?.message || '';
                        if (errMsg.toLowerCase().includes('key') || geminiRes.status === 403 || geminiRes.status === 429) {
                            break;
                        }
                    }
                } catch (fetchErr) {
                    console.warn(`Worker fetch falhou para ${target.model}:`, fetchErr);
                }
            }

            if (!geminiRes) {
                return new Response(JSON.stringify({ error: { message: "Todos os modelos do Gemini estão temporariamente indisponíveis. Tente novamente em instantes." } }), {
                    status: 503,
                    headers: { ...corsHeaders, "Content-Type": "application/json" }
                });
            }

            const data = await geminiRes.json().catch(() => ({}));

            return new Response(JSON.stringify(data), {
                status: geminiRes.status,
                headers: { ...corsHeaders, "Content-Type": "application/json" }
            });
        } catch (err) {
            return new Response(JSON.stringify({ 
                error: { message: "Falha ao processar requisicao no servidor proxy do Coach IA." } 
            }), {
                status: 500,
                headers: { ...corsHeaders, "Content-Type": "application/json" }
            });
        }
    }
};
