import asyncio
import json
import os
import base64
import re
from fastapi import WebSocket
from google import genai
from google.genai import types
from browser import BrowserManager


SYSTEM_PROMPT = """Tu es un agent IA autonome de navigation web pour les démarches administratives au Bénin.
Tu opères sur service-public.bj et les sites officiels béninois.

## MODE DE FONCTIONNEMENT

Tu travailles en boucle autonome : tu effectues UNE micro-action à la fois, puis tu seras rappelé automatiquement avec le nouvel état du navigateur. Tu n'as PAS besoin d'informer l'utilisateur de ce que tu fais — agis, et la boucle continuera d'elle-même.

## L'UNIQUE RÈGLE DE DÉCISION

Pose-toi cette question avant chaque action :
"Est-ce que j'ai besoin d'une information que SEUL l'utilisateur peut me donner ?"

━━━ NON ━━━ → action silencieuse, message = ""
Exemples : popup → click | cookie banner → click | bouton "Suivant" → click | page qui charge → wait | lien à cliquer → click | navigation → navigate

━━━ OUI ━━━ → action: "ask_user", message = question structurée
Exemples : champ "Nom" → ask_user | champ "Date de naissance" → ask_user | champ "NPI" → ask_user

━━━ TÂCHE TERMINÉE ━━━ → action: "respond", message = résumé du résultat

## FORMAT DE RÉPONSE — JSON PUR UNIQUEMENT

{
  "action": "navigate" | "click" | "fill" | "fill_multiple" | "ask_user" | "respond" | "search" | "submit" | "wait" | "scroll",
  "params": {},
  "reasoning": "1 phrase : ce que tu vois et pourquoi tu prends cette décision",
  "message": ""
}

## PARAMÈTRES

- navigate      → {"url": "https://..."}
  ⚡ RÈGLE CRITIQUE (Angular SPA) : Quand tu veux accéder à une page dont tu connais l'URL (visible dans "Liens"),
  utilise TOUJOURS `navigate` plutôt que `click`. Exemple :
  ✅ {"action": "navigate", "url": "https://service-public.bj/public/services/service/PS00373"}
  ❌ {"action": "click", "params": {"selector": "a[href='https://...']"}}  ← ne fonctionne pas sur Angular
  Si la même page s'affiche après un `click`, c'est que le lien Angular n'a pas répondu — passe IMMÉDIATEMENT à `navigate`.
- click         → {"selector": "#css"} OU {"text": "texte exact du bouton"}
  Les boutons sont listés dans "Boutons" avec leur champ `selector` (ex: `#id`, `__btn_index_2`). Utilise `selector` en priorité.
  Si un bouton a `disabled: true`, il y a un champ non-rempli ou une validation manquante — remplis d'abord les champs requis.
  `__btn_index_N` est un sélecteur valide pour les boutons sans id : {"action":"click","params":{"selector":"__btn_index_2"}}
- fill          → {"selector": "#css", "value": "valeur"}
  Pour les `<select>` (type=select-one) : utilise `fill` avec la valeur de l'option (`value`, pas le texte affiché).
  Les options disponibles sont listées dans `allInputs[].options`. Ex: gender → value="M" ou "F"
- fill_multiple → {"fields": [{"selector": "...", "value": "..."}, ...]}
- search        → {"query": "termes"}
- submit        → {"selector": "[type='submit']"} ou {}
- wait          → {"ms": 1500}
- scroll        → {"direction": "down" | "up"}
- ask_user      → params: {"fields": [{"id": "identifiant", "label": "Question précise", "hint": "exemple optionnel"}, ...]}
  Les champs sont présentés UN PAR UN automatiquement côté frontend. message = ""
  Exemple minimal : {"action":"ask_user","params":{"fields":[{"id":"npi","label":"Quel est votre NPI ?","hint":"Ex: 12345678"}]},"reasoning":"...","message":""}
- respond       → {} — message = résultat final uniquement

## SÉLECTEURS (ordre de préférence)

#id > [formcontrolname="..."] > [name="..."] > [placeholder="..."] > [type="..."] > .classe

IMPORTANT : le site est une application Angular. Les champs du formulaire sont listés dans "allInputs" avec leurs attributs réels (id, formcontrolname, name, placeholder, label). Utilise EXACTEMENT les valeurs de `selector` fournies dans allInputs — ne devine jamais un sélecteur.
Si un input a `selector: ""`, utilise son `placeholder` ou son `label` pour construire le sélecteur : `[placeholder="..."]`.

## EXEMPLES CONCRETS — CE QU'IL FAUT FAIRE

SITUATION : Une popup est visible sur la page
✅ CORRECT   → {"action": "click", "params": {"selector": ".modal-close"}, "reasoning": "Popup détectée, je la ferme pour accéder au contenu", "message": ""}
❌ INTERDIT  → {"action": "respond", "params": {}, "reasoning": "...", "message": "Je ferme la fenêtre d'information."}
❌ INTERDIT  → {"action": "ask_user", "params": {}, "reasoning": "...", "message": "Dois-je fermer cette popup ?"}

SITUATION : Deux popups sont visibles
✅ CORRECT   → Ferme la première silencieusement. La boucle se relancera automatiquement pour la deuxième.
❌ INTERDIT  → Annoncer "Je ferme la première fenêtre" et s'arrêter.

SITUATION : Un cookie banner est présent
✅ CORRECT   → {"action": "click", "params": {"text": "Accepter"}, "reasoning": "Cookie banner, j'accepte pour continuer", "message": ""}

SITUATION : Un formulaire demande le nom et la date de naissance
✅ CORRECT   → {"action": "ask_user", "params": {}, "reasoning": "Formulaire avec données personnelles, je demande les informations à l'utilisateur", "message": "Pour votre casier judiciaire, j'ai besoin de :\n- Votre nom complet\n- Votre prénom\n- Votre date de naissance (JJ/MM/AAAA)\n- Votre NPI (numéro personnel d'identification)"}

## 🚫 INTERDICTION ABSOLUE — CONNEXION / CRÉATION DE COMPTE

Sur service-public.bj, il est STRICTEMENT INTERDIT de :
- Créer un compte utilisateur
- Se connecter à un compte existant
- Remplir un champ NPI dans un formulaire de connexion/inscription
- Cliquer sur "Créer un compte", "Se connecter", "Connexion", "S'inscrire", "Continuer avec mon compte"
- Suivre tout flux d'authentification (mot de passe, code SMS, question de sécurité)

Toutes les démarches sur service-public.bj sont accessibles SANS compte, en mode anonyme.
Si le site propose une connexion, IGNORE-LA et trouve le chemin sans authentification.
Si une page de connexion/inscription s'affiche, navigue directement vers l'URL de la démarche demandée.
Si tu te retrouves sur une page de login ou d'inscription : c'est une erreur de navigation — fais `navigate` vers la bonne URL.

✅ CORRECT   → Naviguer directement vers l'URL du service et remplir le formulaire sans compte
❌ INTERDIT  → Cliquer sur "Créer un compte" ou remplir un formulaire d'inscription
❌ INTERDIT  → Demander à l'utilisateur un mot de passe, un code de vérification ou une question de sécurité

## RAPPEL FINAL

- `message` = "" pour navigate, click, fill, fill_multiple, search, submit, wait, scroll
- `message` = "" également pour ask_user (les questions sont dans params.fields)
- `message` = résultat UNIQUEMENT pour respond
- Ne jamais commenter tes actions techniques à l'utilisateur
- Les obstacles (popups, banners, modals) se gèrent seuls, sans demander l'avis de l'utilisateur
- Garde toujours l'objectif initial en tête : traite les obstacles et continue vers le but
- Si après un `click` la page n'a pas changé (même URL, même allInputs), c'est un échec silencieux Angular — utilise `navigate` avec l'URL directe
- Si tu te retrouves de nouveau sur la page d'accueil après une authentification, reprends la démarche initiale avec `navigate`
"""


class NavigationAgent:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.browser = BrowserManager()
        self.history: list[dict] = []
        self.screenshot_task: asyncio.Task | None = None
        self.current_screenshot: str = ""
        self._running = False
        self._user_goal: str = ""

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY non défini")
        self.client = genai.Client(api_key=api_key)
        self.extracted_info: dict = {}            # Données extraites des documents
        self._waiting_for_document = False        # En attente d'upload (frontend)
        self._doc_step: int = 0                   # 0=rien, 1=attend acte, 2=attend CNI, 3=fini
        self._awaiting_confirmation: bool = False         # Attente confirmation réponse utilisateur
        self._next_answer_needs_confirmation: bool = False # Prochaine réponse doit être confirmée
        self._pending_answer: str = ""                    # Réponse en attente de confirmation
        self._filled_fields: dict[str, str] = {}  # Champs déjà remplis (selector → value)
        self._field_queue: list[dict] = []      # File de champs à demander
        self._field_answers: dict[str, str] = {} # Réponses collectées en cours
        self._collecting_fields: bool = False    # Mode collecte séquentielle
        self._current_field: dict = {}           # Champ en cours de saisie
        self._field_total: int = 0               # Nombre total de champs à collecter

    async def initialize(self):
        await self.browser.start()
        self._running = True

        await self.browser.navigate("https://service-public.bj")
        self.screenshot_task = asyncio.create_task(self._stream_screenshots())

        welcome = (
            "Bonjour ! Je suis votre assistant pour les démarches administratives au Bénin. "
            "Que souhaitez-vous faire ?\n"
            "Exemples : \"Je veux faire mon casier judiciaire\", "
            "\"Je veux renouveler mon passeport\", \"Je veux obtenir un acte de naissance\"."
        )
        await self._send({"type": "message", "role": "assistant", "text": welcome})
        self.history.append({"role": "assistant", "text": welcome})

    # ──────────────────────────────────────────────
    # Screenshot streaming
    # ──────────────────────────────────────────────

    async def _stream_screenshots(self):
        while self._running:
            try:
                screenshot = await self.browser.take_screenshot()
                if screenshot:
                    self.current_screenshot = screenshot
                    url = await self.browser.current_url()
                    await self._send({"type": "screenshot", "data": screenshot})
                    await self._send({"type": "url", "url": url})
                await asyncio.sleep(0.8)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Screenshot stream error: {e}")
                await asyncio.sleep(1)

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    async def _send(self, data: dict):
        try:
            await self.websocket.send_json(data)
        except Exception:
            pass

    async def send_status(self, status: str):
        await self._send({"type": "status", "text": status})

    # ──────────────────────────────────────────────
    # Entry points
    # ──────────────────────────────────────────────

    async def process_audio_message(self, audio_data: str, mime_type: str):
        """Transcrit un message audio fongbe et le traduit en français via Gemini."""
        await self.send_status("thinking")
        await self._send({"type": "log", "action": "fill", "text": "🎤 Transcription audio fongbe en cours..."})

        try:
            audio_bytes = base64.b64decode(audio_data)
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    (
                        "L'utilisateur parle en langue fongbe (langue parlée au Bénin, Afrique de l'Ouest). \n"
                        "Ta tâche :\n"
                        "1. Comprends ce que l'utilisateur dit en fongbe.\n"
                        "2. Traduis sa demande en français clair et naturel.\n"
                        "Exemples :\n"
                        "  'Mi jɛ wà dokun mitɔn' → 'Je veux faire mon extrait de naissance'\n"
                        "  'Ðò nɛ̌ e è nɔ wà dokun ɔ gbɔn é ?' → 'Comment faire mon extrait de naissance ?'\n"
                        "  'Mi jɛ wà passpot mitɔn' → 'Je veux faire mon passeport'\n"
                        "Réponds UNIQUEMENT avec la traduction française, sans explication ni préfixe.\n"
                        "Si l'audio est inaudible ou incompréhensible, réponds exactement : AUDIO_INAUDIBLE"
                    ),
                ],
            )
            french_text = response.text.strip() if response.text else ""

            if not french_text or "AUDIO_INAUDIBLE" in french_text:
                await self._send({
                    "type": "message",
                    "role": "assistant",
                    "text": "Je n'ai pas pu comprendre l'audio. Veuillez réessayer ou taper votre demande en français.",
                })
                await self.send_status("idle")
                return

            # Afficher le message traduit dans la conversation comme message utilisateur
            await self._send({"type": "message", "role": "user", "text": french_text})

            # Traiter comme un message utilisateur normal
            await self.process_message(french_text)

        except Exception as e:
            print(f"Erreur transcription audio fongbe: {e}")
            await self._send({
                "type": "message",
                "role": "assistant",
                "text": "Erreur lors de la transcription audio. Veuillez réessayer ou taper votre demande.",
            })
            await self.send_status("idle")

    async def process_message(self, user_text: str):
        self.history.append({"role": "user", "text": user_text})

        # ── Mode collecte de champs séquentiels ─────────────────────────────────
        if self._collecting_fields:
            await self._handle_field_answer(user_text)
            return

        # ── Premier message : mémorise l'objectif et démarre la collecte de docs ──
        if not self._user_goal:
            self._user_goal = user_text
            await self._request_document(step=1)
            return

        # ── L'utilisateur passe un document en tapant du texte ──────────────────
        if self._waiting_for_document:
            self._waiting_for_document = False
            await self._send({"type": "ask_document_done"})
            if self._doc_step == 1:
                # A passé l'acte de naissance → demander la CNI
                await self._request_document(step=2)
                return
            elif self._doc_step == 2:
                # A passé la CNI → démarrer la navigation
                self._doc_step = 3
                await self.send_status("thinking")
                await self._autonomous_loop(max_iterations=30)
                return

        # ── Confirmation d'une réponse en attente ────────────────────────────────
        if self._awaiting_confirmation:
            await self._handle_confirmation(user_text)
            return

        # ── Réponse à une question ask_user → demander confirmation ─────────────
        if self._next_answer_needs_confirmation:
            self._next_answer_needs_confirmation = False
            await self._request_answer_confirmation(user_text)
            return

        # ── Réponse normale → relancer la boucle ────────────────────────────────
        await self.send_status("thinking")
        await self._autonomous_loop(max_iterations=30)

    async def receive_document(self, data: str, mime_type: str):
        """Reçoit un document uploadé et en extrait les informations."""
        self._waiting_for_document = False

        if self._doc_step == 1:
            label = "acte de naissance"
            log_msg = "Lecture de l'acte de naissance en cours..."
        else:
            label = "carte d'identité"
            log_msg = "Lecture de la carte d'identité en cours..."

        await self.send_status("thinking")
        await self._send({"type": "log", "action": "fill", "text": log_msg})

        new_info = await self._extract_document_info(data, mime_type, doc_type=label)
        self.extracted_info.update(new_info)  # merge (CNI peut compléter l'acte)

        if new_info:
            fields = "\n".join(
                f"• {k.replace('_', ' ').capitalize()} : {v}"
                for k, v in new_info.items() if v
            )
            msg = f"Informations extraites de votre {label} :\n{fields}"
        else:
            msg = f"{label.capitalize()} reçu(e). Peu d'informations lisibles, je vous demanderai les champs manquants."

        await self._send({"type": "message", "role": "assistant", "text": msg})
        self.history.append({"role": "assistant", "text": msg})

        if self._doc_step == 1:
            # Acte reçu → demander la CNI
            await self._request_document(step=2)
        else:
            # CNI reçue → démarrer la navigation
            self._doc_step = 3
            await self._send({"type": "ask_document_done"})
            await self.send_status("thinking")
            await self._autonomous_loop(max_iterations=30)

    # ──────────────────────────────────────────────
    # Collecte séquentielle de champs
    # ──────────────────────────────────────────────

    async def _start_field_collection(self, fields: list[dict]):
        """Démarre la collecte séquentielle de champs utilisateur."""
        if not fields:
            return
        self._field_queue = list(fields[1:])   # tout après le premier
        self._field_answers = {}
        self._field_total = len(fields)
        self._collecting_fields = True
        await self._send_field(fields[0])

    async def _send_field(self, field: dict):
        """Envoie un champ au frontend pour affichage inline."""
        self._current_field = field
        index = self._field_total - len(self._field_queue)  # 1-based position
        await self._send({
            "type": "ask_field",
            "field_id": field.get("id", ""),
            "label": field.get("label", ""),
            "hint": field.get("hint", ""),
            "index": index,
            "total": self._field_total,
        })

    async def _handle_field_answer(self, value: str):
        """Traite la réponse d'un champ et passe au suivant si nécessaire."""
        field_id = self._current_field.get("id", "field_0")
        label = self._current_field.get("label", field_id)

        self._field_answers[field_id] = value
        self.extracted_info[field_id] = value  # disponible immédiatement pour Gemini

        if self._field_queue:
            # Champ suivant
            next_field = self._field_queue.pop(0)
            await self._send_field(next_field)
        else:
            # Tous les champs collectés → reprendre la navigation
            self._collecting_fields = False
            answers_str = "\n".join(f"- {k}: {v}" for k, v in self._field_answers.items())
            context = f"Informations fournies par l'utilisateur :\n{answers_str}"
            self.history.append({"role": "user", "text": context})
            self._field_answers = {}
            await self.send_status("thinking")
            await self._autonomous_loop(max_iterations=30)

    async def receive_field_answer(self, field_id: str, value: str):
        """Point d'entrée pour une réponse de champ envoyée directement par le frontend."""
        if self._collecting_fields:
            self.history.append({"role": "user", "text": value})
            await self._handle_field_answer(value)

    async def _request_document(self, step: int):
        self._doc_step = step
        self._waiting_for_document = True
        if step == 1:
            msg = (
                "Pour pré-remplir automatiquement les formulaires, "
                "veuillez d'abord uploader votre acte de naissance (photo ou scan)."
            )
        else:
            msg = (
                "Merci ! Veuillez maintenant uploader votre carte nationale d'identité "
                "(recto ou recto/verso)."
            )
        await self._send({"type": "ask_document", "text": msg})
        await self._send({"type": "message", "role": "assistant", "text": msg})
        self.history.append({"role": "assistant", "text": msg})

    # ──────────────────────────────────────────────
    # Confirmation de réponse utilisateur
    # ──────────────────────────────────────────────

    async def _request_answer_confirmation(self, answer: str):
        """Demande à l'utilisateur de confirmer sa réponse à travers l'UI inline."""
        self._awaiting_confirmation = True
        self._pending_answer = answer
        # Envoyer un évènement structuré au lieu d'un texte brut
        await self._send({
            "type": "ask_confirm",
            "question": "Est-ce bien la bonne valeur ?",
            "value": answer,
        })

    async def _handle_confirmation(self, user_text: str):
        """Traite la réponse de confirmation ou de correction."""
        self._awaiting_confirmation = False
        confirm_words = {"oui", "yes", "ok", "correct", "exactement", "c'est ça",
                         "parfait", "valider", "valide", "confirme", "affirmatif"}
        is_confirmed = any(w in user_text.lower() for w in confirm_words)

        if is_confirmed:
            # La réponse précédente est validée → continuer
            await self.send_status("thinking")
            await self._autonomous_loop(max_iterations=30)
        else:
            # L'utilisateur corrige → demander confirmation sur la nouvelle valeur
            self._pending_answer = user_text
            await self._request_answer_confirmation(user_text)

    async def _extract_document_info(self, data: str, mime_type: str, doc_type: str = "acte de naissance") -> dict:
        """Utilise Gemini Vision pour extraire les champs d'un document d'identité."""
        try:
            if "carte" in doc_type.lower() or "identité" in doc_type.lower() or "cni" in doc_type.lower():
                prompt = (
                    "Extrais les informations de cette carte nationale d'identité béninoise. "
                    "Réponds UNIQUEMENT avec un objet JSON valide (sans markdown) :\n"
                    '{"nom":"","prenoms":"","date_naissance":"","lieu_naissance":"",'
                    '"sexe":"","numero_cni":"","date_expiration_cni":"","adresse":"",'
                    '"npi":"","profession":""}\n'
                    "Mets \"\" pour les champs illisibles ou absents."
                )
            else:
                prompt = (
                    "Extrais les informations de cet acte de naissance béninois. "
                    "Réponds UNIQUEMENT avec un objet JSON valide (sans markdown) :\n"
                    '{"nom":"","prenoms":"","date_naissance":"","lieu_naissance":"",'
                    '"sexe":"","nom_pere":"","nom_mere":"","numero_acte":"","commune":""}\n'
                    "Mets \"\" pour les champs illisibles ou absents."
                )
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(
                        data=base64.b64decode(data), mime_type=mime_type
                    ),
                ],
            )
            text = response.text.strip()
            parsed = self._extract_json(text)
            # Filtre les champs vides
            return {k: v for k, v in (parsed or {}).items() if v}
        except Exception as e:
            print(f"[Document extraction error] {e}")
            return {}

    # ──────────────────────────────────────────────
    # Autonomous action loop
    # ──────────────────────────────────────────────

    async def _autonomous_loop(self, max_iterations: int = 30):
        consecutive_respond = 0
        last_error: str = ""
        # Stuck detection: track last N (action, params_key) pairs
        recent_actions: list[str] = []

        for _ in range(max_iterations):
            page_info = await self.browser.get_page_info()
            action_data = await self._call_gemini(page_info, last_error=last_error)

            if action_data is None:
                await self._send({
                    "type": "message",
                    "role": "assistant",
                    "text": "Une erreur s'est produite. Veuillez réessayer.",
                })
                break

            action = action_data.get("action", "respond")
            params = action_data.get("params", {})

            # Stuck detection: same action+params repeated, or 2-step cycle
            action_key = f"{action}:{json.dumps(params, sort_keys=True, ensure_ascii=False).lower()}"
            recent_actions.append(action_key)
            if len(recent_actions) > 6:
                recent_actions.pop(0)
            # Detect: same action 4x in a row, OR alternating 2-step cycle (ABABABAB)
            stuck_4x = len(recent_actions) == 4 and len(set(recent_actions)) == 1
            stuck_cycle = (
                len(recent_actions) == 6
                and len(set(recent_actions)) <= 2
                and recent_actions[0] == recent_actions[2] == recent_actions[4]
                and recent_actions[1] == recent_actions[3] == recent_actions[5]
            )
            if stuck_4x or stuck_cycle:
                await self._send({
                    "type": "message",
                    "role": "assistant",
                    "text": "Je semble bloqué sur cette étape. Pouvez-vous m'indiquer comment procéder ou me donner des informations supplémentaires ?",
                })
                break

            success = await self._execute_action(action_data)

            # Si l'action a échoué, on le dit à Gemini pour qu'il change d'approche
            if not success and action in ("click", "fill", "fill_multiple", "submit"):
                # Detect Angular SPA silent navigation failure: click param has href
                has_href_selector = 'href' in str(params.get('selector', '')) or 'href' in str(params.get('text', ''))
                if has_href_selector:
                    last_error = (
                        f"L'action '{action}' ({params}) a échoué (application Angular SPA). "
                        f"Utilise IMMÉDIATEMENT l'action `navigate` avec l'URL du lien. "
                        f"Exemple : {{\"action\":\"navigate\",\"url\":\"https://...\"}}. "
                        f"Ne réessaie JAMAIS click sur un lien Angular."
                    )
                else:
                    last_error = (
                        f"L'action '{action}' ({params}) a échoué : élément introuvable ou non visible. "
                        f"Change d'approche : utilise 'selector' avec un sélecteur de la liste Boutons (ex: __btn_index_N), "
                        f"essaie un autre sélecteur CSS (préfère [formcontrolname=\"...\"] pour Angular), "
                        f"ou fais d'abord un scroll."
                    )
            else:
                last_error = ""

            # Seul ask_user arrête immédiatement la boucle
            if action == "ask_user":
                break

            # respond : on laisse passer une fois (Gemini peut l'utiliser à tort
            # pour une action triviale), mais deux fois de suite = vraiment terminé
            if action == "respond":
                consecutive_respond += 1
                if consecutive_respond >= 2:
                    break
            else:
                consecutive_respond = 0

            await asyncio.sleep(0.4)

        await self.send_status("idle")

    # ──────────────────────────────────────────────
    # Gemini API call
    # ──────────────────────────────────────────────

    async def _call_gemini(self, page_info: dict, last_error: str = "") -> dict | None:
        history_str = json.dumps(self.history[-14:], ensure_ascii=False, indent=2)

        # Debug: always print what the DOM reports for forms
        forms = page_info.get('forms', [])
        if forms:
            print(f"\n[DOM forms] {json.dumps(forms, ensure_ascii=False)}\n")

        all_inputs = page_info.get('allInputs', [])
        if all_inputs:
            print(f"\n[DOM allInputs] {json.dumps(all_inputs, ensure_ascii=False)}\n")

        page_str = (
            f"Page actuelle :\n"
            f"- URL    : {page_info.get('url', '')}\n"
            f"- Titre  : {page_info.get('title', '')}\n"
            f"- Formulaires : {json.dumps(forms, ensure_ascii=False)}\n"
            f"- Inputs visibles : {json.dumps(all_inputs, ensure_ascii=False)}\n"
            f"- Boutons     : {json.dumps(page_info.get('buttons', [])[:10], ensure_ascii=False)}\n"
            f"- Liens       : {json.dumps(page_info.get('links', [])[:15], ensure_ascii=False)}\n"
            f"- Texte visible : {page_info.get('bodyText', '')[:1800]}"
        )

        error_str = (
            f"\n\n⚠️ DERNIÈRE ACTION ÉCHOUÉE : {last_error}\n"
            f"Tu DOIS changer d'approche, ne répète pas la même action."
        ) if last_error else ""

        doc_str = ""
        if self.extracted_info:
            doc_str = (
                f"\n\nINFORMATIONS DISPONIBLES (extraites de l'acte de naissance) :\n"
                f"{json.dumps(self.extracted_info, ensure_ascii=False, indent=2)}\n"
                f"Utilise ces données pour remplir les champs correspondants dans les formulaires. "
                f"Demande à l'utilisateur UNIQUEMENT les champs que tu ne trouves pas ici."
            )

        filled_str = ""
        if self._filled_fields:
            lines = "\n".join(f"  • {sel} = \"{val}\"" for sel, val in self._filled_fields.items())
            filled_str = (
                f"\n\n✅ CHAMPS DÉJÀ REMPLIS DANS CETTE SESSION (NE PAS RE-REMPLIR) :\n"
                f"{lines}\n"
                f"Ces champs ont été saisis avec succès. Ignore-les et passe aux champs suivants "
                f"ou au bouton Suivant/Soumettre si tous les champs requis sont remplis."
            )

        prompt = (
            f"OBJECTIF UTILISATEUR : {self._user_goal}\n\n"
            f"Historique de conversation :\n{history_str}\n\n"
            f"{page_str}"
            f"{doc_str}"
            f"{filled_str}"
            f"{error_str}\n\n"
            f"Analyse l'état actuel et retourne la prochaine micro-action."
        )

        try:
            parts: list = [types.Part.from_text(text=prompt)]
            if self.current_screenshot:
                parts.append(
                    types.Part.from_bytes(
                        data=base64.b64decode(self.current_screenshot),
                        mime_type="image/jpeg",
                    )
                )

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.5-flash",
                contents=parts,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                ),
            )

            response_text = response.text.strip()
            print(f"\n[Gemini raw] {response_text[:500]}\n")

            parsed = self._extract_json(response_text)
            if parsed is None:
                print(f"[Gemini] Impossible d'extraire le JSON. Réponse complète :\n{response_text}")
            return parsed

        except Exception as e:
            import traceback
            print(f"[Gemini error] {e}\n{traceback.format_exc()}")
            return None

    def _extract_json(self, text: str) -> dict | None:
        """Extrait un objet JSON d'une réponse Gemini, même si elle contient du markdown."""
        # 1. Essai direct
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Retire les balises markdown ```json ... ```
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3. Cherche le premier { ... } complet dans la réponse
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    # ──────────────────────────────────────────────
    # Action execution
    # ──────────────────────────────────────────────

    async def _execute_action(self, action_data: dict) -> bool:
        """Exécute l'action et retourne True si succès, False si échec."""
        action = action_data.get("action", "respond")
        params = action_data.get("params", {})
        message = action_data.get("message", "").strip()
        ok = True

        status_map = {
            "navigate":     "navigation",
            "click":        "clicking",
            "fill":         "filling",
            "fill_multiple":"filling",
            "search":       "searching",
            "submit":       "clicking",
            "wait":         "thinking",
            "scroll":       "navigation",
            "ask_user":     "idle",
            "respond":      "idle",
        }
        await self.send_status(status_map.get(action, "idle"))

        # Envoie le raisonnement avant d'exécuter l'action
        reasoning = action_data.get("reasoning", "").strip()
        if reasoning:
            await self._send({"type": "log", "action": action, "text": reasoning})

        if action == "navigate":
            ok = await self.browser.navigate(params.get("url", ""))
            if ok:
                self._filled_fields.clear()  # Reset on page change

        elif action == "click":
            selector = params.get("selector")
            text = params.get("text")
            if selector:
                ok = await self.browser.click_by_selector(selector)
                if not ok and text:
                    ok = await self.browser.click_by_text(text)
            elif text:
                ok = await self.browser.click_by_text(text)
            else:
                ok = False

        elif action == "fill":
            sel = params.get("selector", "")
            val = params.get("value", "")
            ok = await self.browser.fill_field(sel, val)
            # Only track if value actually appears in DOM (prevents false positives)
            if ok and sel:
                actual = await self.browser.page.evaluate(
                    "([s]) => document.querySelector(s)?.value || ''", [sel]
                )
                if actual:
                    self._filled_fields[sel] = actual

        elif action == "fill_multiple":
            for field in params.get("fields", []):
                sel = field.get("selector", "")
                val = field.get("value", "")
                r = await self.browser.fill_field(sel, val)
                if r and sel:
                    actual = await self.browser.page.evaluate(
                        "([s]) => document.querySelector(s)?.value || ''", [sel]
                    )
                    if actual:
                        self._filled_fields[sel] = actual
                if not r:
                    ok = False
                await asyncio.sleep(0.25)

        elif action == "search":
            query = params.get("query", "")
            # Use the visible search box on the page, then press Enter
            filled = await self.browser.fill_field(
                '[placeholder="Trouver un service"]', query
            )
            if filled:
                await self.browser.page.keyboard.press("Enter")
                await asyncio.sleep(2.0)
                ok = True
            else:
                # Fallback: navigate to search URL
                url = f"https://service-public.bj/public/recherche?q={query.replace(' ', '+')}"
                ok = await self.browser.navigate(url)

        elif action == "submit":
            selector = params.get("selector", "[type='submit']")
            ok = await self.browser.click_by_selector(selector)
            if ok:
                await asyncio.sleep(2)

        elif action == "scroll":
            direction = params.get("direction", "down")
            delta = 600 if direction == "down" else -600
            await self.browser.page.evaluate(f"window.scrollBy(0, {delta})")

        elif action == "wait":
            await asyncio.sleep(min(params.get("ms", 1000) / 1000, 5))

        # ask_user : démarrer la collecte séquentielle de champs
        if action == "ask_user":
            fields = params.get("fields", [])
            if not fields:
                # Fallback: message texte brut → un seul champ générique
                q = message or "Veuillez fournir l'information demandée."
                fields = [{"id": "field_0", "label": q, "hint": ""}]
            await self._start_field_collection(fields)
            ok = True

        # respond : message final OU liste d'informations à demander
        if action == "respond" and message:
            # Détection : Gemini liste des infos nécessaires au lieu d'utiliser ask_user
            lines = [l.strip() for l in message.split("\n") if l.strip().startswith("-") or l.strip().startswith("•")]
            if len(lines) >= 2 and any(kw in message.lower() for kw in
                                       ["besoin", "fournir", "indiquer", "préciser", "manquant"]):
                # Auto-conversion en ask_user séquentiel
                fields = []
                for i, line in enumerate(lines):
                    text = line.lstrip("-• ").strip()
                    # Nettoyer le markdown gras
                    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
                    fields.append({"id": f"info_{i}", "label": text, "hint": ""})
                if fields:
                    await self._start_field_collection(fields)
                    ok = True
                    # Ne pas envoyer le message text dans ce cas
                    return ok
            # Message final normal
            await self._send({"type": "message", "role": "assistant", "text": message})
            self.history.append({"role": "assistant", "text": message})

        return ok

    # ──────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────

    async def close(self):
        self._running = False
        if self.screenshot_task:
            self.screenshot_task.cancel()
            try:
                await self.screenshot_task
            except asyncio.CancelledError:
                pass
        await self.browser.close()
