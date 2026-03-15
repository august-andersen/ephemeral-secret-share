def get_viewer_html() -> str:
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ephemeral Secret</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #0a0a0a;
    color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
.card {
    max-width: 480px;
    width: 90%;
    text-align: center;
    padding: 2.5rem 2rem;
}
.lock { font-size: 2.5rem; margin-bottom: 1rem; }
h1 { font-size: 1.4rem; font-weight: 600; margin-bottom: 0.75rem; }
.sub { color: #888; font-size: 0.9rem; line-height: 1.5; margin-bottom: 1.5rem; }
#reveal-btn {
    background: #fff;
    color: #0a0a0a;
    border: none;
    padding: 0.75rem 2rem;
    font-size: 1rem;
    font-weight: 600;
    border-radius: 6px;
    cursor: pointer;
    transition: opacity 0.15s;
}
#reveal-btn:hover { opacity: 0.85; }
#secret-box {
    display: none;
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 1.25rem;
    margin-top: 1.5rem;
    text-align: left;
}
#secret-text {
    font-family: "SF Mono", "Fira Code", "Fira Mono", Menlo, Consolas, monospace;
    font-size: 0.9rem;
    word-break: break-all;
    white-space: pre-wrap;
    color: #f0f0f0;
    line-height: 1.5;
}
#copy-btn {
    margin-top: 1rem;
    background: transparent;
    color: #888;
    border: 1px solid #444;
    padding: 0.5rem 1.25rem;
    font-size: 0.85rem;
    border-radius: 4px;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
}
#copy-btn:hover { color: #fff; border-color: #666; }
.error { color: #ff6b6b; }
.deleted { color: #888; font-size: 0.85rem; margin-top: 1rem; }
.footer {
    position: fixed;
    bottom: 1rem;
    color: #444;
    font-size: 0.75rem;
}
.footer a { color: #555; text-decoration: none; }
.footer a:hover { color: #777; }
</style>
</head>
<body>
<div class="card">
    <div class="lock">&#x1f512;</div>
    <h1 id="title">You\'ve received a secret.</h1>
    <p class="sub" id="subtitle">This secret can only be viewed once. After you reveal it, it will be permanently deleted.</p>
    <button id="reveal-btn" onclick="revealSecret()">Reveal Secret</button>
    <div id="secret-box">
        <div id="secret-text"></div>
        <button id="copy-btn" onclick="copySecret()">Copy to clipboard</button>
        <p class="deleted">This secret has been deleted from the server.</p>
    </div>
</div>
<div class="footer"><a href="https://github.com/august-andersen/ephemeral-secret-share">ephemeral-secret-share</a></div>
<script>
const pathParts = window.location.pathname.split('/');
const secretId = pathParts[pathParts.length - 1];
const keyB64url = window.location.hash.substring(1);

if (!keyB64url) {
    document.getElementById('title').textContent = 'Invalid link.';
    document.getElementById('subtitle').textContent = 'No decryption key found in the URL.';
    document.getElementById('reveal-btn').style.display = 'none';
}

function b64urlToBytes(b64url) {
    let b64 = b64url.replace(/-/g, '+').replace(/_/g, '/');
    while (b64.length % 4) b64 += '=';
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
}

async function revealSecret() {
    const btn = document.getElementById('reveal-btn');
    btn.disabled = true;
    btn.textContent = 'Decrypting...';

    try {
        const resp = await fetch('/api/secret/' + secretId);
        if (!resp.ok) {
            document.getElementById('title').textContent = 'Secret not found.';
            document.getElementById('subtitle').textContent = 'This secret has already been viewed or does not exist.';
            document.getElementById('subtitle').classList.add('error');
            btn.style.display = 'none';
            return;
        }

        const data = await resp.json();
        if (data.expired) {
            document.getElementById('title').textContent = 'Secret expired.';
            document.getElementById('subtitle').textContent = 'This secret has expired.';
            document.getElementById('subtitle').classList.add('error');
            btn.style.display = 'none';
            return;
        }

        const stored = Uint8Array.from(atob(data.ciphertext), c => c.charCodeAt(0));
        const iv = stored.slice(0, 12);
        const ctWithTag = stored.slice(12);

        const keyBytes = b64urlToBytes(keyB64url);
        const cryptoKey = await crypto.subtle.importKey(
            'raw', keyBytes, { name: 'AES-GCM' }, false, ['decrypt']
        );

        const plainBuf = await crypto.subtle.decrypt(
            { name: 'AES-GCM', iv: iv }, cryptoKey, ctWithTag
        );

        const plaintext = new TextDecoder().decode(plainBuf);
        document.getElementById('secret-text').textContent = plaintext;
        document.getElementById('secret-box').style.display = 'block';
        btn.style.display = 'none';
        document.getElementById('title').textContent = 'Secret revealed.';
        document.getElementById('subtitle').textContent = '';
    } catch (e) {
        document.getElementById('title').textContent = 'Decryption failed.';
        document.getElementById('subtitle').textContent = 'The decryption key may be invalid or the data is corrupted.';
        document.getElementById('subtitle').classList.add('error');
        btn.style.display = 'none';
    }
}

async function copySecret() {
    const text = document.getElementById('secret-text').textContent;
    try {
        await navigator.clipboard.writeText(text);
        document.getElementById('copy-btn').textContent = 'Copied!';
        setTimeout(() => { document.getElementById('copy-btn').textContent = 'Copy to clipboard'; }, 2000);
    } catch {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        document.getElementById('copy-btn').textContent = 'Copied!';
        setTimeout(() => { document.getElementById('copy-btn').textContent = 'Copy to clipboard'; }, 2000);
    }
}
</script>
</body>
</html>'''
