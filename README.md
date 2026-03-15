# ephemeral-secret-share

Share secrets via one-time links. Client-side encrypted. Self-hosted. Zero dependencies on external services.

## How it works

- You run `ess "my-secret"` — it encrypts the secret locally with AES-256-GCM, starts a web server, and gives you a one-time link.
- The encryption key lives only in the URL fragment (`#...`), which browsers never send to the server. The server only stores the ciphertext.
- The recipient opens the link, clicks "Reveal Secret", and the browser decrypts the secret client-side using the Web Crypto API.
- After one view, the ciphertext is permanently deleted from server memory. The link is dead.

## Installation

With [pipx](https://pipx.pypa.io/) (recommended):

```
pipx install git+https://github.com/august-andersen/ephemeral-secret-share.git
```

With pip:

```
pip install git+https://github.com/august-andersen/ephemeral-secret-share.git
```

From source:

```
git clone https://github.com/august-andersen/ephemeral-secret-share.git
cd ephemeral-secret-share
pipx install .
```

## Usage

```bash
# Share a secret
ess "sk-ant-abc123-my-api-key"

# With expiry
ess "my-secret" --expires 1h
ess "my-secret" --expires 30m

# Custom port
ess "my-secret" --port 9090

# Pipe support
echo "my-secret" | ess

# Interactive prompt (hidden input)
ess
```

## Security

- **AES-256-GCM** authenticated encryption — integrity and confidentiality.
- Encryption and decryption happen **client-side only** (Python CLI and browser).
- The server stores and serves only ciphertext. It never sees the plaintext or the key.
- The encryption key is in the **URL fragment** (`#...`), which is [never sent to the server](https://www.rfc-editor.org/rfc/rfc3986#section-3.5) by browsers.
- Secrets are stored **in memory only** — lost when the server stops.
- Each secret is **deleted immediately** after being retrieved once.

## License

MIT
