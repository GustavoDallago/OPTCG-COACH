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

        const apiKey = env.GEMINI_API_KEY;
        if (!apiKey) {
            return new Response(JSON.stringify({ 
                error: { message: "GEMINI_API_KEY nao configurada nas variaveis de ambiente do Cloudflare Worker." } 
            }), {
                status: 500,
                headers: { ...corsHeaders, "Content-Type": "application/json" }
            });
        }

        // Se acessar via GET (pelo navegador), retorna a lista de modelos suportados para essa chave
        if (request.method === "GET") {
            try {
                const listRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(apiKey)}`);
                const listData = await listRes.json();
                return new Response(JSON.stringify(listData, null, 2), {
                    status: listRes.status,
                    headers: { ...corsHeaders, "Content-Type": "application/json" }
                });
            } catch (err) {
                return new Response(JSON.stringify({ error: err.message }), {
                    status: 500,
                    headers: { ...corsHeaders, "Content-Type": "application/json" }
                });
            }
        }

        if (request.method !== "POST") {
            return new Response(JSON.stringify({ error: "Metodo nao permitido" }), {
                status: 405,
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

            const candidateTargets = [];
            if (body.model && typeof body.model === 'string') {
                const customModel = body.model.replace(/^models\//, '').trim();
                candidateTargets.push({ ver: "v1beta", model: customModel });
                candidateTargets.push({ ver: "v1", model: customModel });
            }
            candidateTargets.push(
                { ver: "v1beta", model: "gemini-3.6-flash" },
                { ver: "v1", model: "gemini-3.6-flash" },
                { ver: "v1beta", model: "gemini-2.5-flash" },
                { ver: "v1", model: "gemini-2.5-flash" },
                { ver: "v1beta", model: "gemini-2.5-flash-lite" },
                { ver: "v1", model: "gemini-2.5-flash-lite" }
            );

            // Evita duplicatas preservando a ordem
            const uniqueTargets = [];
            const seen = new Set();
            for (const t of candidateTargets) {
                if (!seen.has(t.model)) {
                    seen.add(t.model);
                    uniqueTargets.push(t);
                }
            }

            let geminiRes = null;
            const attempts = [];

            for (const target of uniqueTargets) {
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

                    const errJson = await geminiRes.clone().json().catch(() => ({}));
                    const errMsg = errJson.error?.message || '';
                    attempts.push({ model: target.model, status: geminiRes.status, message: errMsg });

                    // Se for erro definitivo de chave de API inválida, encerra
                    if (geminiRes.status === 400 || geminiRes.status === 403) {
                        if (errMsg.toLowerCase().includes('key') || errMsg.toLowerCase().includes('api_key')) {
                            break;
                        }
                    }

                    // Se for 404 (modelo não suportado), 503 (sobrecarga) ou outro, tenta o próximo modelo
                    continue;
                } catch (fetchErr) {
                    attempts.push({ model: target.model, error: fetchErr.message });
                }
            }

            if (!geminiRes || !geminiRes.ok) {
                const lastData = geminiRes ? await geminiRes.json().catch(() => ({})) : {};
                const finalMsg = lastData.error?.message || (attempts.length > 0 ? attempts[attempts.length - 1].message : "Nenhum modelo Gemini respondeu.");
                return new Response(JSON.stringify({ 
                    error: { 
                        message: finalMsg,
                        attempts: attempts
                    } 
                }), {
                    status: geminiRes ? geminiRes.status : 503,
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
