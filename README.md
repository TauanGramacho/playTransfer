# PlayTransfer

PlayTransfer transfere playlists entre Spotify, Deezer, YouTube Music, SoundCloud, Apple Music, TIDAL e Amazon Music.

Este repositório mantém dois modos bem separados:

- **Local/desktop:** habilita automações nativas, janelas guiadas, captura via navegador e fallbacks manuais. É o modo para devs baixarem e usarem no próprio PC.
- **Cloud/Fly:** desliga automações nativas, porque servidor não tem o navegador gráfico do usuário. Em produção, cada plataforma precisa de OAuth oficial ou device code.

## Rodar Localmente

Requisitos:

- Python 3.12+
- Chrome ou Edge instalado para os fluxos guiados de navegador
- Conta logada nos serviços que você quer testar

Passos:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.exemplo .env
python app.py
```

Abra:

```txt
http://127.0.0.1:5001
```

Por padrão, rodando localmente, o app retorna:

```txt
is_cloud=false
native_automation_available=true
```

Isso mantém disponíveis os fluxos que dependem do PC do dev, como Deezer por janela/cookie local, SoundCloud por janela local e YouTube Music guiado.

## Variáveis Úteis

As variáveis abaixo são opcionais para desenvolvimento local, mas melhoram os fluxos oficiais:

```env
BASE_URL=http://127.0.0.1:5001
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
YTMUSIC_OAUTH_CLIENT_ID=
YTMUSIC_OAUTH_CLIENT_SECRET=
DEEZER_APP_ID=
DEEZER_SECRET_KEY=
SOUNDCLOUD_CLIENT_ID=
SOUNDCLOUD_CLIENT_SECRET=
AMAZON_MUSIC_API_KEY=
AMAZON_LWA_CLIENT_ID=
AMAZON_LWA_CLIENT_SECRET=
```

Para abrir o navegador automaticamente ao iniciar:

```env
PLAYTRANSFER_OPEN_BROWSER=1
```

Para simular produção/cloud localmente:

```env
PLAYTRANSFER_CLOUD=1
```

## Status Por Plataforma No Modo Local

- **Spotify:** funciona com OAuth oficial se `SPOTIFY_CLIENT_ID` estiver configurado; também possui fallbacks locais.
- **Deezer:** funciona localmente com automação/cookie `arl`; OAuth oficial precisa de `DEEZER_APP_ID` e `DEEZER_SECRET_KEY`.
- **YouTube Music:** funciona com OAuth/device code se configurado; também tem fallback manual/guiado local.
- **SoundCloud:** funciona localmente com automação nativa; OAuth oficial precisa de `SOUNDCLOUD_CLIENT_ID` e `SOUNDCLOUD_CLIENT_SECRET`.
- **Apple Music:** usa token público para leitura e fluxos MusicKit/manual para escrita.
- **TIDAL:** usa device code.
- **Amazon Music:** local pode usar captura de sessão; produção depende de Amazon Music Web API liberada.

## Produção No Fly

No Fly, as automações nativas ficam desligadas:

```txt
native_automation_available=false
```

Isso é intencional. Produção não deve tentar abrir Chrome, Edge ou pywebview dentro do servidor.

Para configurar credenciais em produção:

```bash
fly secrets set BASE_URL="https://playtransfer-io.fly.dev" -a playtransfer-io
```

Exemplos:

```bash
fly secrets set SPOTIFY_CLIENT_ID="..." -a playtransfer-io
fly secrets set YTMUSIC_OAUTH_CLIENT_ID="..." YTMUSIC_OAUTH_CLIENT_SECRET="..." -a playtransfer-io
fly secrets set SOUNDCLOUD_CLIENT_ID="..." SOUNDCLOUD_CLIENT_SECRET="..." -a playtransfer-io
fly secrets set DEEZER_APP_ID="..." DEEZER_SECRET_KEY="..." -a playtransfer-io
fly secrets set AMAZON_MUSIC_API_KEY="..." AMAZON_LWA_CLIENT_ID="..." AMAZON_LWA_CLIENT_SECRET="..." -a playtransfer-io
```

Depois:

```bash
fly deploy -a playtransfer-io
```

## Verificação Rápida

```bash
python -m py_compile app.py services\youtube_music.py
node --check static\js\app.js
python -c "import app; c=app.app.test_client(); print(c.get('/api/platforms').get_json()['_meta'])"
```

Em modo local, a última linha deve mostrar `is_cloud: False` e `native_automation_available: True`.
