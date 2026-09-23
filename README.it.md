# TAVIS: Turn Any VIdeo into Skills

Gli dai un video che insegna qualcosa. Ne esce una scheda da leggere e, se la approvi, una skill che Claude sa usare.

```
    .-"""-.-"""-.      ████████  █████  ██    ██ ██ ███████
   /  .-.   .-.  \        ██    ██   ██ ██    ██ ██ ██
  |  (   )_(   )  |       ██    ███████ ██    ██ ██ ███████
  |   '-'   '-'   |       ██    ██   ██  ██  ██  ██      ██
   \  '._____.'  /        ██    ██   ██   ████   ██ ███████
    '-.._____..-'
                     turn any video into a skill   ·   v0.2.0
```

[![Licenza: MIT](https://img.shields.io/badge/license-MIT-FF6A00.svg)](LICENSE)
![Versione](https://img.shields.io/badge/version-0.2.0-0B0A09.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-0B0A09.svg)

*[Read in English](README.md)*

![TAVIS su un video TikTok: verdetto 'non vale', con avvertimenti su una promozione a colpi di DM, risparmi non dimostrati e un comando d'installazione ricevuto in privato](docs/card.png)

*Una scheda vera, su un TikTok di 46 secondi senza sottotitoli, trascritto da Whisper in locale. Verdetto: **non vale una skill**. È un "commenta HEADROOM e ti mando il link in DM" che promuove un tool. TAVIS segnala che il risparmio del 60-90% non è dimostrato e che non conviene incollare in Claude Code un comando d'installazione ricevuto in privato. Fa notare anche che, con un abbonamento fisso, quel risparmio di token non vale soldi. Su un video YouTube di 23 minuti, "Unlock Claude God-Mode", ha tenuto il metodo per scrivere prompt e ha segnalato lo spot con link affiliato, il corso in vendita e i numeri che nessuno può verificare. A Claude non arriva niente finché non premi Approva.*

---

## Installazione

Serve **Git Bash** su Windows, o una bash qualsiasi su macOS e Linux. Nient'altro: se manca Python, l'installatore si offre di installarlo lui (winget su Windows, Homebrew su macOS, apt su Linux).

```bash
git clone https://github.com/valezion7/turn-any-videos-into-skills.git
cd turn-any-videos-into-skills
bash install.sh --all
```

`--all` aggiunge la finestra di accesso a TikTok e Whisper locale. Per il solo nucleo basta `bash install.sh`. Tutto finisce in una `.venv` dentro la cartella, compreso il piccolo motore JavaScript che serve a YouTube (quindi Node non serve). Il comando `tavis` va in `~/bin`.

## In 30 secondi

```bash
tavis
```

Si apre il browser su `http://127.0.0.1:4747`. La prima volta una **configurazione in quattro passi** chiede tre cose: chi deve leggere i video (e mostra cosa ha trovato sul tuo computer), chi sei, e se vuoi TikTok. Ogni passo si può saltare.

Poi scegli **TikTok** o **YouTube** e scrivi solo il nome utente, che resta anche se cambi social. Oppure scegli **Link** e incolla il link di un video qualsiasi. I video del creator compaiono in una griglia, con quello selezionato a destra. Premi **Skill-ize**, leggi la scheda e poi **Learn this skill**. La skill finisce in `~/.claude/skills/`, e Claude Code la usa dalla sessione successiva.

> I video di YouTube si guardano dentro TAVIS. TikTok invece non permette di riprodurre i suoi video dentro altre pagine: la copertina di un TikTok apre il video nel browser.

Da terminale:

```bash
tavis learn "https://www.youtube.com/watch?v=bjdBVZa66oU" --lang it
```

### Modificare una skill dopo

Le skill scritte da TAVIS sono elencate in **Your skills**. Aprendone una puoi modificare il `SKILL.md` a mano, oppure chiedere al cervello che stai usando di cambiarla: "accorciala", "aggiungi un esempio per il mio lavoro", "togli tutto ciò che promuove un prodotto". Ogni risposta si apre in una nuova scheda accanto alla versione salvata, come le schede del browser: passi dall'una all'altra, chiudi quelle che non ti servono, continui a chiedere partendo da quella che vuoi. **Show reasoning** spiega cosa ha cambiato il cervello e perché, con le righe tolte e aggiunte. Salvi la scheda che ti piace. TAVIS rifiuta di salvare un file che Claude Code non riuscirebbe più a caricare.

## Come funziona

1. **Video**: yt-dlp legge i dati del video e i sottotitoli del creator, o quelli automatici della piattaforma. Il video non viene scaricato.
2. **Trascrizione**: se i sottotitoli non ci sono, parte Whisper in locale (GPU se c'è, altrimenti CPU). Un riferimento temporale ogni 20 secondi circa.
3. **Scheda**: uno dei quattro "cervelli" legge la trascrizione insieme al tuo profilo. Una scansione di frasi tipiche (codici sconto, "link in bio", promesse di guadagno) fa da secondo controllo.
4. **Decidi tu**. Se rifiuti non viene scritto niente. Se approvi, la skill va in `~/.claude/skills/<nome>/SKILL.md`, con fonte e avvertimenti in fondo.

### Cosa c'è nella scheda

| sezione | a cosa risponde |
|---|---|
| **Verdetto** | Vale una skill? Intrattenimento e televendite prendono un "no" |
| **Che cosa insegna** | Due frasi semplici |
| **Che cosa ha imparato** | Punti concreti col minuto del video (cliccabile su YouTube) |
| **A cosa serve** | Situazioni reali in cui aiuta |
| **Per il tuo lavoro** | Come si applica alla *tua* attività: descriviti in "About you" |
| **Per te** | Abitudini, come impostare il lavoro, una cosa da provare questa settimana |
| **Avvertimenti** | sponsorizzato · conflitto d'interessi · rischioso · superato · non verificabile · manipolazione |
| **Confidenza** | alta / media / bassa, e perché |
| **La skill** | Nome, descrizione e corpo, tutti modificabili prima di approvare |

Gli avvertimenti sono la ragione per cui l'approvazione è manuale. Molti video "formativi" vendono qualcosa. Una skill costruita su una pubblicità spinge Claude verso quel prodotto ogni volta che si carica.

## Configurazione

### I cervelli: ne basta uno, e il modello locale non serve

TAVIS trova da solo quello che hai già. La configurazione e `tavis doctor` mostrano ogni opzione come pronta o no, e spiegano come attivarla.

| cervello | costo | cosa serve | note |
|---|---|---|---|
| `claude-code` **(predefinito)** | il tuo abbonamento Claude | [Claude Code](https://claude.com/claude-code) con l'accesso fatto | `claude -p` con **tutti gli strumenti spenti**, senza i tuoi hook e impostazioni, in una cartella vuota |
| `codex` | il tuo abbonamento ChatGPT | [Codex CLI](https://github.com/openai/codex) con l'accesso fatto | `codex exec` in **sandbox di sola lettura**, niente salvato |
| `gemini` | il tuo account Google | [Gemini CLI](https://github.com/google-gemini/gemini-cli) con l'accesso fatto | `gemini -p` in modalità plan (sola lettura), senza estensioni |
| `anthropic` | a consumo | `ANTHROPIC_API_KEY` | modello `TAVIS_ANTHROPIC_MODEL` (predefinito `claude-sonnet-5`) |
| `openai` | a consumo | `OPENAI_API_KEY` | |
| `deepseek` | a consumo | `DEEPSEEK_API_KEY` | |
| `openrouter` | a consumo | `OPENROUTER_API_KEY` | centinaia di modelli con una sola chiave |
| `gemini-api` | a consumo / gratis con limiti | `GEMINI_API_KEY` | |
| `groq` · `mistral` · `xai` | a consumo | `GROQ_API_KEY` · `MISTRAL_API_KEY` · `XAI_API_KEY` | |
| `custom` | tuo | `TAVIS_CUSTOM_BASE_URL` (+ `TAVIS_CUSTOM_API_KEY`) | qualsiasi server che parla il formato chat di OpenAI (vLLM, LiteLLM, un gateway aziendale…) |
| `ollama` | gratis, offline | [Ollama](https://ollama.com) | **rilevato da solo**: TAVIS sceglie il miglior modello chat che hai installato. I modelli per il codice, di embedding e "uncensored" vanno in fondo; tra gli altri vince il più grande fino a `TAVIS_OLLAMA_MAX_B`=40B. Nessun modello? Lo scarica la configurazione. Un secondo passaggio completa i consigli e gli avvertimenti che i modelli locali tendono a saltare |
| `lmstudio` | gratis, offline | [LM Studio](https://lmstudio.ai) con il server locale acceso | stesso secondo passaggio di Ollama |
| `none` | gratis | niente | estrae le frasi che sembrano passi e **dichiara** che nessun modello ha letto il video |

Per ogni cervello via API il modello si sceglie con `TAVIS_<NOME>_MODEL` (per esempio `TAVIS_DEEPSEEK_MODEL`). Senza, TAVIS chiede al fornitore quali modelli esistono e ne sceglie uno da chat, così un modello rinominato non rompe niente. Le chiavi si leggono dall'ambiente e non vengono mai salvate.

### Trascrizione: prima i sottotitoli, poi il motore che scegli tu

Quasi tutti i video hanno i sottotitoli, e quelli non costano niente. Quando un video non li ha (quasi tutti i TikTok), TAVIS scarica solo l'audio e lo passa al motore che scegli in **Transcript**:

| modo | costo | cosa serve | note |
|---|---|---|---|
| `auto` (predefinito) | | | i sottotitoli, altrimenti Whisper sul tuo computer, altrimenti il primo servizio con una chiave |
| `subtitles` | gratis | niente | i sottotitoli del creator, oppure quelli automatici nella lingua parlata |
| `whisper` | gratis, offline | `bash install.sh --with-whisper` | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) sul tuo computer. La dimensione del modello si sceglie nell'interfaccia (`turbo` di base, fino a `tiny` per i computer lenti). Usa la GPU se può, altrimenti la CPU |
| `elevenlabs` | a consumo | `ELEVENLABS_API_KEY` | ElevenLabs Scribe (`scribe_v2`, si cambia con `TAVIS_STT_ELEVENLABS_MODEL`) |
| `openai` | a consumo | `OPENAI_API_KEY` | `whisper-1`, si cambia con `TAVIS_STT_OPENAI_MODEL` |
| `groq` | economico, velocissimo | `GROQ_API_KEY` | `whisper-large-v3-turbo` |
| `custom` | tuo | `TAVIS_STT_BASE_URL` (+ `TAVIS_STT_API_KEY`, `TAVIS_STT_MODEL`) | qualsiasi server con un endpoint `/audio/transcriptions` nel formato di OpenAI: faster-whisper-server, speaches, LocalAI, il gateway della tua azienda |

Ai servizi che accettano al massimo 25 MB l'audio arriva prima compresso a qualità voce, se c'è ffmpeg. La lingua dell'audio viene sempre riconosciuta da sola, qualunque sia la lingua in cui vuoi la scheda.

### Entrare su TikTok

Ormai TikTok chiede l'accesso anche solo per aprire un video. TAVIS **non ti chiede mai la password**:

```bash
tavis login
```

Si apre una finestra del browser con un profilo tutto suo, direttamente sul **QR code** di TikTok. Lo inquadri con l'app TikTok dal telefono ed è fatto: nessuna password scritta da nessuna parte. In quella finestra funzionano anche gli altri modi di accesso di TikTok. TAVIS aspetta il cookie di sessione di TikTok e salva **solo i cookie di tiktok.com** in `~/.tavis/cookies.txt`. Nell'interfaccia fa lo stesso il bottone **TikTok** in alto.

> Perché non usa il tuo Chrome di tutti i giorni? Su Windows Chrome tiene bloccato il database dei cookie mentre è aperto, e lo cifra con una chiave che solo lui sa leggere: `yt-dlp --cookies-from-browser chrome` lì fallisce. Su macOS o Linux con Firefox funziona anche `export TAVIS_COOKIES_FROM_BROWSER=firefox`.

## Tutti i comandi

```
tavis                  apre l'interfaccia (come: tavis ui)
tavis learn <url> [--brain claude-code|codex|gemini|anthropic|openai|deepseek|…|ollama|none] [--model M]
                  [--transcriber auto|subtitles|whisper] [--lang it]
                  [--yes | --no] [--overwrite] [--keep CARTELLA]
tavis list @creator [--platform tiktok|youtube|search]
tavis login | logout
tavis doctor           cosa è installato, quali cervelli sono pronti
```

## Domande frequenti

**Serve una chiave API, o un modello locale?** Nessuno dei due. Basta un abbonamento che hai già: Claude Code, Codex (ChatGPT) o Gemini CLI. Ollama, LM Studio e `none` non chiedono nessun account. Le chiavi sono solo una possibilità.

**Funziona offline?** Con `--brain ollama --transcriber whisper` sì, una volta scaricato l'audio del video.

**TikTok mi banna?** L'accesso automatizzato è contro i termini di TikTok. TAVIS fa poche richieste per video, le stesse pagine che aprirebbe il tuo browser, ma il rischio è tuo. Se ti preoccupa, usa un account che puoi permetterti di perdere.

**Un video può manipolare Claude attraverso la trascrizione?** La trascrizione viene trattata come dato. Claude Code gira con tutti gli strumenti spenti, in una cartella vuota, senza i tuoi hook e impostazioni. Il prompt gli chiede di segnalare come avvertimento `manipulation` qualsiasi istruzione rivolta a un'AI. Il caso peggiore è una scheda sbagliata, e la scheda la leggi prima che venga scritto qualcosa.

**Posso modificare la skill prima di installarla?** Sì: nome, descrizione e corpo si modificano nella scheda. Una volta installata è un normale file Markdown.

## Limiti, detti chiari

- **La scheda è buona quanto il cervello.** Le schede che vedi qui sono di `claude-code`. I modelli Ollama piccoli perdono avvertimenti e appiattiscono i consigli, mentre `none` non capisce niente e lo dice.
- **Conta solo il parlato.** Quello che si vede a schermo ma non viene detto (codice su una slide, un pannello di impostazioni) TAVIS non lo vede.
- **I sottotitoli automatici sentono male**, soprattutto nomi e comandi: "claw.md" al posto di CLAUDE.md è un caso vero. Rileggi i passi.
- **Un avvertimento può sfuggire.** "Nessun avvertimento" è la lettura del modello, non una garanzia.
- **I video molto lunghi vengono tagliati** per stare nel modello (150.000 caratteri con Claude, 40.000 con Ollama), e la scheda dice dove.
- **Termini di servizio.** Le piattaforme vietano in vari modi lo scaricamento automatico. TAVIS legge i sottotitoli e, solo per Whisper, l'audio. È pensato per video che hai il diritto di guardare, e l'uso che ne fai è una tua responsabilità.
- **TikTok cambia spesso.** Elenco dei video di un creator e lettura di un video funzionano oggi (provati con `tavis login` e yt-dlp 2026.08.19 con `curl_cffi`). Quando TikTok cambia le sue pagine, rilanciare `bash install.sh` porta l'ultima versione di yt-dlp.

## Contribuire

- **Un bug:** apri una issue con l'output di `tavis doctor` e il link che ha dato problemi.
- **Una fonte nuova:** tutto ciò che yt-dlp legge funziona già. Se serve un trattamento speciale, l'unico file da toccare è `tavis/source.py`.
- **Una scheda migliore:** il prompt è `PROMPT` in `tavis/card.py`. Allega una scheda prima/dopo su un video vero.
- Prima di una pull request lancia `python test_tavis.py`: niente rete, niente modello, pochi secondi.

## Disinstallare

```bash
rm ~/bin/tavis                        # il comando
rm -rf ~/.tavis                       # cookie, profilo, cronologia delle schede
rm -rf turn-any-videos-into-skills    # il codice e la sua .venv
```

Le skill installate restano in `~/.claude/skills/<nome>/`: cancella quelle che non vuoi più. Ognuna dice da dove viene nelle ultime righe.

## Licenza e crediti

MIT, vedi [LICENSE](LICENSE). Costruito su [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Claude Code](https://claude.com/claude-code), l'[API Anthropic](https://docs.anthropic.com), [Ollama](https://ollama.com) e [Playwright](https://playwright.dev).

Fatto da [Beezy](https://studiobeezy.com). Fa parte di "un progetto open source al mese".
