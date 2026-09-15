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
                    maxOutputTokens: 2500
                }
            };

            const primaryModel = "gemini-3.6-flash";
            let geminiRes = await fetch(
                `https://generativelanguage.googleapis.com/v1beta/models/${primaryModel}:generateContent?key=${encodeURIComponent(apiKey)}`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                }
            );

            // Fallback caso gemini-3.6-flash retorne 404
            if (!geminiRes.ok && geminiRes.status === 404) {
                geminiRes = await fetch(
                    `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=${encodeURIComponent(apiKey)}`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    }
                );
            }

            const data = await geminiRes.json();

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
