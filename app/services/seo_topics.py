"""Obsah verejných tématických stránok „anglické slovíčka na tému X“.

SEO kanál: každá téma je samostatná indexovateľná stránka s reálnou sadou
slovíčok, príkladmi použitia a CTA na registráciu. Cieľom sú long-tail dopyty
typu „anglické slovíčka v reštaurácii“, kde je konkurencia oveľa nižšia než
pri všeobecnom „učenie angličtiny“.

Rozšírenie o novú tému = nový záznam v `TOPICS`. Šablóna aj routa sú spoločné,
sitemap sa napĺňa automaticky.

Zámerne SK→EN: primárny trh je SK/CZ (pozri komerčné hodnotenie v TODO.md).
Štruktúra záznamu už počíta s ďalšími pármi cez `lang_from`/`lang_to`.

Polia:
    slug        — URL (`/slovicka/{slug}`), bez diakritiky
    title       — <title> a H1
    description — meta description (~150–160 znakov)
    intro       — odstavec nad tabuľkou, unikátny text (nie duplicita)
    words       — [{en, sk, example}] — príklad je veta s daným slovom
    tips        — praktické poznámky pod tabuľkou (odrážky)
    related     — slugy príbuzných tém (interné prelinkovanie)
    date        — ISO dátum poslednej úpravy, ide do sitemapy ako <lastmod>
"""

LANG_FROM = "en"
LANG_TO = "sk"

TOPICS = [
    {
        "slug": "v-restauracii",
        "title": "Anglické slovíčka: v reštaurácii",
        "description": (
            "Anglické slovíčka do reštaurácie s výslovnosťou v príkladoch — "
            "objednávanie, jedálny lístok, platenie. 20 slov aj s vetami."
        ),
        "intro": (
            "Objednať si jedlo po anglicky je jedna z prvých situácií, do ktorej sa "
            "dostanete v zahraničí. Nepotrebujete na to celú gramatiku — stačí "
            "dvadsiatka slov a pár fráz, ktoré sa opakujú v každej reštaurácii od "
            "Londýna po New York. Nižšie nájdete presne tie, ktoré počujete najčastejšie, "
            "vždy aj s vetou, v ktorej slovo naozaj zaznie."
        ),
        "words": [
            {"en": "starter", "sk": "predjedlo", "example": "We ordered a starter to share."},
            {"en": "main course", "sk": "hlavné jedlo", "example": "What would you like as a main course?"},
            {"en": "dessert", "sk": "dezert", "example": "I'm too full for dessert."},
            {"en": "menu", "sk": "jedálny lístok", "example": "Could we see the menu, please?"},
            {"en": "waiter", "sk": "čašník", "example": "The waiter brought our drinks."},
            {"en": "to order", "sk": "objednať si", "example": "Are you ready to order?"},
            {"en": "bill", "sk": "účet", "example": "Could we have the bill, please?"},
            {"en": "tip", "sk": "sprepitné", "example": "We left a ten percent tip."},
            {"en": "booking", "sk": "rezervácia", "example": "I have a booking for two at eight."},
            {"en": "table for two", "sk": "stôl pre dvoch", "example": "Do you have a table for two?"},
            {"en": "starving", "sk": "vyhladnutý", "example": "I'm starving — let's eat."},
            {"en": "side dish", "sk": "príloha", "example": "Chips come as a side dish."},
            {"en": "rare", "sk": "krvavý (steak)", "example": "I'd like my steak rare."},
            {"en": "well done", "sk": "prepečený", "example": "She always orders her meat well done."},
            {"en": "vegetarian", "sk": "vegetariánsky", "example": "Do you have any vegetarian options?"},
            {"en": "allergic to", "sk": "alergický na", "example": "I'm allergic to nuts."},
            {"en": "takeaway", "sk": "jedlo so sebou", "example": "We got a takeaway on the way home."},
            {"en": "to split the bill", "sk": "rozdeliť si účet", "example": "Shall we split the bill?"},
            {"en": "refill", "sk": "dolievanie zadarmo", "example": "Free refills on all soft drinks."},
            {"en": "cutlery", "sk": "príbor", "example": "Could I have some clean cutlery?"},
        ],
        "tips": [
            "V Británii sa predjedlo povie <strong>starter</strong>, v USA skôr <strong>appetizer</strong> — obe vám všade porozumejú.",
            "<strong>Bill</strong> je britský účet, Američan povie <strong>check</strong>.",
            "Sprepitné v USA sa očakáva (15–20 %), v Británii býva už zarátané ako <em>service charge</em> — všimnite si to na účte.",
        ],
        "related": ["v-hoteli", "jedlo-a-potraviny", "cestovanie-a-letisko"],
        "date": "2026-08-13",
    },
    {
        "slug": "cestovanie-a-letisko",
        "title": "Anglické slovíčka: cestovanie a letisko",
        "description": (
            "Anglické slovíčka na letisko a cestovanie — check-in, batožina, "
            "odlet, colnica. 20 slov s príkladmi, ktoré počujete na každom letisku."
        ),
        "intro": (
            "Na letisku je angličtina neúprosná: hlásenia sú rýchle, nápisy stručné a "
            "nikto vám nič nezopakuje. Dobrá správa je, že slovná zásoba je veľmi "
            "uzavretá — tie isté výrazy nájdete v Viedni, Dubaji aj Londýne. Keď "
            "poznáte týchto dvadsať, prejdete letiskom bez stresu."
        ),
        "words": [
            {"en": "departure", "sk": "odlet", "example": "Check the departure board for your gate."},
            {"en": "arrival", "sk": "prílet", "example": "Arrivals are on the ground floor."},
            {"en": "boarding pass", "sk": "palubný lístok", "example": "Have your boarding pass ready."},
            {"en": "gate", "sk": "brána (nástupná)", "example": "Boarding at gate 14."},
            {"en": "check-in", "sk": "odbavenie", "example": "Online check-in opens 24 hours before."},
            {"en": "luggage", "sk": "batožina", "example": "My luggage didn't arrive."},
            {"en": "hand luggage", "sk": "príručná batožina", "example": "Hand luggage must fit under the seat."},
            {"en": "delay", "sk": "meškanie", "example": "The flight has a two-hour delay."},
            {"en": "to board", "sk": "nastúpiť do lietadla", "example": "We board in ten minutes."},
            {"en": "aisle seat", "sk": "sedadlo pri uličke", "example": "I prefer an aisle seat."},
            {"en": "window seat", "sk": "sedadlo pri okne", "example": "She always takes the window seat."},
            {"en": "customs", "sk": "colnica", "example": "Nothing to declare at customs."},
            {"en": "passport control", "sk": "pasová kontrola", "example": "The queue at passport control was long."},
            {"en": "connecting flight", "sk": "nadväzujúci let", "example": "I missed my connecting flight."},
            {"en": "one-way ticket", "sk": "jednosmerný lístok", "example": "A one-way ticket to Dublin, please."},
            {"en": "return ticket", "sk": "spiatočný lístok", "example": "A return ticket is cheaper."},
            {"en": "to land", "sk": "pristáť", "example": "We land at half past six."},
            {"en": "to take off", "sk": "vzlietnuť", "example": "The plane took off on time."},
            {"en": "security check", "sk": "bezpečnostná kontrola", "example": "Take your laptop out at the security check."},
            {"en": "baggage claim", "sk": "výdaj batožiny", "example": "Meet me at baggage claim."},
        ],
        "tips": [
            "<strong>Luggage</strong> je nepočítateľné — nikdy nie <em>luggages</em>. Jeden kus je <em>a piece of luggage</em>.",
            "Britské <strong>queue</strong> (rad) je slovo, ktoré na letiskách počujete stále — Američan povie <strong>line</strong>.",
            "Hlásenie „<em>final call</em>“ znamená posledné volanie — vtedy už treba bežať.",
        ],
        "related": ["v-hoteli", "v-restauracii", "nakupovanie"],
        "date": "2026-08-13",
    },
    {
        "slug": "v-hoteli",
        "title": "Anglické slovíčka: v hoteli",
        "description": (
            "Anglické slovíčka do hotela — rezervácia, izba, recepcia, raňajky. "
            "20 slov s príkladovými vetami na ubytovanie v zahraničí."
        ),
        "intro": (
            "Hotelová angličtina je zdvorilá a predvídateľná — recepčný sa opýta na to "
            "isté v Ríme aj v Edinburghu. Ak zvládnete rezerváciu, prihlásenie a pár "
            "otázok o izbe, vybavíte ubytovanie bez toho, aby ste museli prepnúť do "
            "posunkovej reči."
        ),
        "words": [
            {"en": "reception", "sk": "recepcia", "example": "Leave your key at reception."},
            {"en": "to check in", "sk": "prihlásiť sa (ubytovať)", "example": "You can check in after 2 p.m."},
            {"en": "to check out", "sk": "odhlásiť sa", "example": "We check out tomorrow morning."},
            {"en": "single room", "sk": "jednolôžková izba", "example": "I booked a single room."},
            {"en": "double room", "sk": "dvojlôžková izba", "example": "A double room for three nights, please."},
            {"en": "en suite", "sk": "s vlastnou kúpeľňou", "example": "All rooms are en suite."},
            {"en": "vacancy", "sk": "voľná izba", "example": "The sign said 'No vacancies'."},
            {"en": "fully booked", "sk": "úplne obsadené", "example": "Sorry, we're fully booked."},
            {"en": "breakfast included", "sk": "raňajky v cene", "example": "Is breakfast included?"},
            {"en": "wake-up call", "sk": "budenie telefónom", "example": "Could I have a wake-up call at six?"},
            {"en": "room service", "sk": "izbová služba", "example": "We ordered room service."},
            {"en": "housekeeping", "sk": "upratovanie", "example": "Housekeeping comes every morning."},
            {"en": "key card", "sk": "kartový kľúč", "example": "My key card doesn't work."},
            {"en": "lift", "sk": "výťah (brit.)", "example": "The lift is out of order."},
            {"en": "ground floor", "sk": "prízemie", "example": "The bar is on the ground floor."},
            {"en": "deposit", "sk": "záloha", "example": "They asked for a deposit."},
            {"en": "to extend the stay", "sk": "predĺžiť pobyt", "example": "Can we extend our stay by one night?"},
            {"en": "complaint", "sk": "sťažnosť", "example": "I'd like to make a complaint."},
            {"en": "air conditioning", "sk": "klimatizácia", "example": "The air conditioning is too cold."},
            {"en": "luggage storage", "sk": "úschovňa batožiny", "example": "Do you have luggage storage?"},
        ],
        "tips": [
            "Britské <strong>ground floor</strong> je naše prízemie, <em>first floor</em> je prvé poschodie. V USA je <em>first floor</em> už prízemie — pozor pri hľadaní izby.",
            "<strong>Lift</strong> je britský výťah, americký je <strong>elevator</strong>.",
            "Fráza „<em>Could I have…?</em>“ znie zdvorilejšie než „<em>I want…</em>“ — v hoteli sa vždy oplatí.",
        ],
        "related": ["cestovanie-a-letisko", "v-restauracii", "cislovky"],
        "date": "2026-08-13",
    },
    {
        "slug": "u-lekara",
        "title": "Anglické slovíčka: u lekára a zdravie",
        "description": (
            "Anglické slovíčka u lekára — príznaky, bolesť, lieky, objednanie. "
            "20 slov s vetami, ktoré potrebujete, keď v zahraničí ochoriete."
        ),
        "intro": (
            "Toto je slovná zásoba, ktorú si nikto neželá použiť — a práve preto ju "
            "väčšina ľudí nemá. Pritom stačí ochorieť na dovolenke a zrazu potrebujete "
            "presne opísať, čo vás bolí. Nasledujúce slová pokrývajú bežnú návštevu "
            "u lekára aj lekárne."
        ),
        "words": [
            {"en": "appointment", "sk": "objednanie (termín)", "example": "I'd like to make an appointment."},
            {"en": "GP", "sk": "všeobecný lekár", "example": "You should see your GP first."},
            {"en": "symptom", "sk": "príznak", "example": "How long have you had these symptoms?"},
            {"en": "pain", "sk": "bolesť", "example": "I have a sharp pain in my back."},
            {"en": "sore throat", "sk": "bolesť hrdla", "example": "I've got a sore throat."},
            {"en": "headache", "sk": "bolesť hlavy", "example": "She has a terrible headache."},
            {"en": "fever", "sk": "horúčka", "example": "He's running a fever."},
            {"en": "cough", "sk": "kašeľ", "example": "The cough keeps me awake."},
            {"en": "rash", "sk": "vyrážka", "example": "A rash appeared on my arm."},
            {"en": "prescription", "sk": "recept (na lieky)", "example": "The doctor gave me a prescription."},
            {"en": "pharmacy", "sk": "lekáreň", "example": "Is there a pharmacy nearby?"},
            {"en": "painkiller", "sk": "liek proti bolesti", "example": "Take a painkiller if it hurts."},
            {"en": "dose", "sk": "dávka", "example": "Don't exceed the daily dose."},
            {"en": "side effect", "sk": "vedľajší účinok", "example": "Drowsiness is a common side effect."},
            {"en": "insurance card", "sk": "kartička poistenca", "example": "Please show your insurance card."},
            {"en": "to feel sick", "sk": "byť na vracanie", "example": "I feel sick after eating."},
            {"en": "to sprain", "sk": "vytknúť si", "example": "I sprained my ankle."},
            {"en": "swollen", "sk": "opuchnutý", "example": "My knee is swollen."},
            {"en": "emergency room", "sk": "pohotovosť", "example": "They took him to the emergency room."},
            {"en": "to recover", "sk": "zotaviť sa", "example": "It took a week to recover."},
        ],
        "tips": [
            "Pozor na falošného priateľa: <strong>sick</strong> v britskej angličtine znamená „na vracanie“, nie len „chorý“. Chorý je <em>ill</em>.",
            "<strong>GP</strong> = <em>general practitioner</em>, teda obvodný lekár — skratka sa používa úplne bežne.",
            "Britská pohotovosť sa volá <strong>A&amp;E</strong> (<em>accident and emergency</em>), americká <strong>ER</strong>.",
        ],
        "related": ["telo", "pocasie", "rodina"],
        "date": "2026-08-13",
    },
    {
        "slug": "pracovny-pohovor",
        "title": "Anglické slovíčka: pracovný pohovor a životopis",
        "description": (
            "Anglické slovíčka na pracovný pohovor — životopis, skúsenosti, "
            "silné stránky, plat. 20 slov s vetami z reálnych pohovorov."
        ),
        "intro": (
            "Pohovor v angličtine sa nevyhráva bohatou slovnou zásobou, ale istotou v "
            "tej správnej. Personalisti sa pýtajú na prekvapivo úzky okruh vecí a "
            "používajú pritom stále tie isté výrazy. Naučte sa ich a namiesto "
            "prekladania v hlave sa budete môcť sústrediť na odpoveď."
        ),
        "words": [
            {"en": "CV / résumé", "sk": "životopis", "example": "Please attach your CV."},
            {"en": "cover letter", "sk": "motivačný list", "example": "The cover letter should be short."},
            {"en": "job opening", "sk": "voľné pracovné miesto", "example": "I saw the job opening online."},
            {"en": "to apply for", "sk": "uchádzať sa o", "example": "I applied for the marketing role."},
            {"en": "applicant", "sk": "uchádzač", "example": "We had forty applicants."},
            {"en": "experience", "sk": "skúsenosti", "example": "She has five years of experience."},
            {"en": "skills", "sk": "zručnosti", "example": "List your technical skills."},
            {"en": "strengths", "sk": "silné stránky", "example": "What are your greatest strengths?"},
            {"en": "weaknesses", "sk": "slabé stránky", "example": "Tell me about your weaknesses."},
            {"en": "background", "sk": "vzdelanie a prax", "example": "Tell us about your background."},
            {"en": "notice period", "sk": "výpovedná lehota", "example": "I have a two-month notice period."},
            {"en": "salary expectations", "sk": "platové očakávania", "example": "What are your salary expectations?"},
            {"en": "benefits", "sk": "zamestnanecké výhody", "example": "The benefits include a company car."},
            {"en": "full-time", "sk": "na plný úväzok", "example": "It's a full-time position."},
            {"en": "part-time", "sk": "na čiastočný úväzok", "example": "He works part-time."},
            {"en": "probation period", "sk": "skúšobná doba", "example": "There's a three-month probation period."},
            {"en": "to be promoted", "sk": "byť povýšený", "example": "She was promoted last year."},
            {"en": "deadline", "sk": "termín odovzdania", "example": "We always meet our deadlines."},
            {"en": "team player", "sk": "tímový hráč", "example": "I'd describe myself as a team player."},
            {"en": "to look forward to", "sk": "tešiť sa na", "example": "I look forward to hearing from you."},
        ],
        "tips": [
            "V Británii sa životopis povie <strong>CV</strong>, v USA <strong>résumé</strong> — a americké <em>CV</em> znamená dlhý akademický životopis.",
            "Formálny e-mail zakončite frázou „<em>I look forward to hearing from you</em>“ — je to štandard, nie zdvorilostná fráza navyše.",
            "Na otázku o slabých stránkach sa neodpovedá „<em>I have none</em>“ — očakáva sa konkrétna vec a to, ako na nej pracujete.",
        ],
        "related": ["skola", "cislovky", "rodina"],
        "date": "2026-08-13",
    },
    {
        "slug": "nakupovanie",
        "title": "Anglické slovíčka: nakupovanie a obchod",
        "description": (
            "Anglické slovíčka na nakupovanie — veľkosti, skúšanie, zľavy, "
            "platenie, reklamácia. 20 slov s príkladovými vetami."
        ),
        "intro": (
            "Nakupovanie je situácia, kde stačí päť fráz a zvládnete celý obchod — "
            "od otázky na veľkosť po reklamáciu. Väčšina slov je navyše taká, ktorú "
            "poznáte z etikiet a výkladov, len ste si ju nikdy vedome nezapamätali."
        ),
        "words": [
            {"en": "shop assistant", "sk": "predavač", "example": "Ask the shop assistant."},
            {"en": "changing room", "sk": "skúšobná kabínka", "example": "The changing rooms are over there."},
            {"en": "to try on", "sk": "vyskúšať si", "example": "Can I try this on?"},
            {"en": "size", "sk": "veľkosť", "example": "Do you have it in a larger size?"},
            {"en": "it fits", "sk": "sedí (padne)", "example": "This jacket fits perfectly."},
            {"en": "receipt", "sk": "pokladničný blok", "example": "Keep the receipt."},
            {"en": "discount", "sk": "zľava", "example": "There's a 20% discount today."},
            {"en": "sale", "sk": "výpredaj", "example": "I bought it in the sale."},
            {"en": "bargain", "sk": "výhodná kúpa", "example": "Ten euros? That's a bargain."},
            {"en": "to afford", "sk": "dovoliť si (finančne)", "example": "I can't afford it."},
            {"en": "cash", "sk": "hotovosť", "example": "Do you take cash?"},
            {"en": "to pay by card", "sk": "platiť kartou", "example": "I'd like to pay by card."},
            {"en": "change", "sk": "výdavok (drobné)", "example": "Here's your change."},
            {"en": "checkout", "sk": "pokladňa", "example": "There's a queue at the checkout."},
            {"en": "trolley", "sk": "nákupný vozík", "example": "Grab a trolley at the entrance."},
            {"en": "refund", "sk": "vrátenie peňazí", "example": "I'd like a refund, please."},
            {"en": "to exchange", "sk": "vymeniť (tovar)", "example": "Can I exchange this for a smaller one?"},
            {"en": "faulty", "sk": "chybný", "example": "The zip is faulty."},
            {"en": "out of stock", "sk": "vypredané", "example": "Sorry, it's out of stock."},
            {"en": "expiry date", "sk": "dátum spotreby", "example": "Check the expiry date."},
        ],
        "tips": [
            "Britské <strong>trolley</strong> je americký <strong>cart</strong>; britský <strong>till</strong> je americký <strong>checkout</strong>.",
            "<strong>Change</strong> znamená aj „drobné“, aj „zmena“ — z kontextu je to vždy jasné.",
            "Pri reklamácii pomôže veta „<em>It's faulty and I'd like a refund</em>“ — krátka a jednoznačná.",
        ],
        "related": ["jedlo-a-potraviny", "cislovky", "v-restauracii"],
        "date": "2026-08-13",
    },
    {
        "slug": "jedlo-a-potraviny",
        "title": "Anglické slovíčka: jedlo a potraviny",
        "description": (
            "Anglické slovíčka o jedle — ovocie, zelenina, mäso, pečivo, "
            "varenie. 20 základných slov s vetami na každodenné použitie."
        ),
        "intro": (
            "Jedlo je téma, ktorá sa v angličtine objaví skôr než akákoľvek iná — "
            "v učebnici, v obchode aj v konverzácii. Tieto slová tvoria jadro, na "
            "ktoré sa dá neskôr nabaliť čokoľvek ďalšie, od receptov po jedálny lístok."
        ),
        "words": [
            {"en": "vegetables", "sk": "zelenina", "example": "Eat more vegetables."},
            {"en": "fruit", "sk": "ovocie", "example": "Fruit is cheaper in summer."},
            {"en": "meat", "sk": "mäso", "example": "I don't eat red meat."},
            {"en": "poultry", "sk": "hydina", "example": "Poultry is in the next aisle."},
            {"en": "dairy", "sk": "mliečne výrobky", "example": "She avoids dairy."},
            {"en": "bread", "sk": "chlieb", "example": "We're out of bread."},
            {"en": "flour", "sk": "múka", "example": "Add two cups of flour."},
            {"en": "wheat", "sk": "pšenica", "example": "This bread contains wheat."},
            {"en": "beans", "sk": "fazuľa", "example": "Beans on toast is a classic."},
            {"en": "cabbage", "sk": "kapusta", "example": "Cabbage is very cheap."},
            {"en": "cucumber", "sk": "uhorka", "example": "Slice the cucumber thinly."},
            {"en": "grapes", "sk": "hrozno", "example": "These grapes are seedless."},
            {"en": "to boil", "sk": "variť (vo vode)", "example": "Boil the potatoes for 20 minutes."},
            {"en": "to fry", "sk": "smažiť", "example": "Fry the onions first."},
            {"en": "to bake", "sk": "piecť", "example": "She bakes bread every Sunday."},
            {"en": "recipe", "sk": "recept (kuchársky)", "example": "It's my grandmother's recipe."},
            {"en": "ingredient", "sk": "prísada", "example": "The main ingredient is butter."},
            {"en": "leftovers", "sk": "zvyšky jedla", "example": "We ate the leftovers for lunch."},
            {"en": "tasty", "sk": "chutný", "example": "That soup was really tasty."},
            {"en": "spicy", "sk": "pikantný", "example": "It's too spicy for me."},
        ],
        "tips": [
            "<strong>Fruit</strong> je zvyčajne nepočítateľné — „<em>a lot of fruit</em>“, nie <em>fruits</em> (to sa používa pre druhy ovocia).",
            "Falošný priateľ: <strong>recipe</strong> je kuchársky recept, lekársky recept je <strong>prescription</strong>.",
            "<strong>Spicy</strong> znamená pálivý aj korenistý — ak myslíte „ostrý“, povedzte <em>hot</em>.",
        ],
        "related": ["v-restauracii", "nakupovanie", "telo"],
        "date": "2026-08-13",
    },
    {
        "slug": "rodina",
        "title": "Anglické slovíčka: rodina a príbuzní",
        "description": (
            "Anglické slovíčka o rodine — príbuzenské vzťahy, svokrovci, "
            "súrodenci. 20 slov s vetami vrátane zložitejších vzťahov."
        ),
        "intro": (
            "Rodinné vzťahy patria medzi prvé témy v každej učebnici, ale väčšina "
            "kurzov skončí pri „mother“ a „brother“. Pritom práve svokrovci, nevlastní "
            "súrodenci a bratranci sú tam, kde angličtina funguje inak než slovenčina "
            "— a kde sa najčastejšie chybuje."
        ),
        "words": [
            {"en": "parents", "sk": "rodičia", "example": "My parents live nearby."},
            {"en": "siblings", "sk": "súrodenci", "example": "Do you have any siblings?"},
            {"en": "relative", "sk": "príbuzný", "example": "We have relatives in Canada."},
            {"en": "cousin", "sk": "bratranec / sesternica", "example": "My cousin is getting married."},
            {"en": "nephew", "sk": "synovec", "example": "I'm babysitting my nephew."},
            {"en": "niece", "sk": "neter", "example": "His niece is only three."},
            {"en": "aunt", "sk": "teta", "example": "Aunt Mary is coming for dinner."},
            {"en": "uncle", "sk": "strýko", "example": "My uncle taught me to drive."},
            {"en": "grandparents", "sk": "starí rodičia", "example": "We visit our grandparents every Sunday."},
            {"en": "mother-in-law", "sk": "svokra", "example": "My mother-in-law is lovely."},
            {"en": "father-in-law", "sk": "svokor", "example": "Her father-in-law is a doctor."},
            {"en": "stepfather", "sk": "nevlastný otec", "example": "His stepfather raised him."},
            {"en": "only child", "sk": "jedináčik", "example": "She's an only child."},
            {"en": "twins", "sk": "dvojčatá", "example": "They're identical twins."},
            {"en": "to get married", "sk": "vziať sa", "example": "They got married in June."},
            {"en": "to be engaged", "sk": "byť zasnúbený", "example": "We've been engaged for a year."},
            {"en": "divorced", "sk": "rozvedený", "example": "My parents are divorced."},
            {"en": "to raise (children)", "sk": "vychovávať", "example": "She raised three children alone."},
            {"en": "to take after", "sk": "podobať sa (na rodiča)", "example": "He takes after his father."},
            {"en": "to get on well", "sk": "dobre vychádzať", "example": "I get on well with my sister."},
        ],
        "tips": [
            "<strong>Cousin</strong> je bratranec aj sesternica — angličtina rod nerozlišuje.",
            "Svokrovci sa tvoria príponou <strong>-in-law</strong>; množné číslo je <em>mothers-in-law</em>, nie <em>mother-in-laws</em>.",
            "<strong>To take after</strong> znamená podobať sa povahou či výzorom na príbuzného — nie „nasledovať niekoho“.",
        ],
        "related": ["u-lekara", "skola", "pracovny-pohovor"],
        "date": "2026-08-13",
    },
    {
        "slug": "pocasie",
        "title": "Anglické slovíčka: počasie",
        "description": (
            "Anglické slovíčka o počasí — dážď, sneh, teplota, predpoveď. "
            "20 slov s vetami na tému, ktorou Briti začínajú každý rozhovor."
        ),
        "intro": (
            "O počasí sa v angličtine hovorí neúmerne veľa — v Británii je to "
            "spoločenský rituál, ktorým sa začína rozhovor s hocikým. Preto sa oplatí "
            "vedieť viac než len „it's raining“: rozdiel medzi mrholením a lejakom "
            "poviete jedným slovom."
        ),
        "words": [
            {"en": "forecast", "sk": "predpoveď", "example": "The forecast says rain."},
            {"en": "cloudy", "sk": "zamračené", "example": "It's cloudy but warm."},
            {"en": "sunny", "sk": "slnečno", "example": "A sunny afternoon at last."},
            {"en": "drizzle", "sk": "mrholenie", "example": "It's only a drizzle."},
            {"en": "shower", "sk": "prehánka", "example": "Scattered showers this afternoon."},
            {"en": "downpour", "sk": "lejak", "example": "We got caught in a downpour."},
            {"en": "thunderstorm", "sk": "búrka", "example": "A thunderstorm woke me up."},
            {"en": "lightning", "sk": "blesk", "example": "Lightning struck the tree."},
            {"en": "fog", "sk": "hmla", "example": "Thick fog closed the airport."},
            {"en": "frost", "sk": "mráz", "example": "There was frost on the car."},
            {"en": "freezing", "sk": "mrazivo", "example": "It's freezing outside."},
            {"en": "mild", "sk": "mierny (teplý)", "example": "A mild winter this year."},
            {"en": "humid", "sk": "vlhký (dusný)", "example": "It's hot and humid."},
            {"en": "breeze", "sk": "vánok", "example": "There's a nice breeze."},
            {"en": "gale", "sk": "víchrica", "example": "Gales are expected tonight."},
            {"en": "to clear up", "sk": "vyjasniť sa", "example": "It should clear up by noon."},
            {"en": "temperature", "sk": "teplota", "example": "The temperature dropped overnight."},
            {"en": "below zero", "sk": "pod nulou", "example": "It's five degrees below zero."},
            {"en": "heatwave", "sk": "vlna horúčav", "example": "The heatwave lasted a week."},
            {"en": "puddle", "sk": "mláka", "example": "The kids jumped in the puddles."},
        ],
        "tips": [
            "Počasie sa opisuje neosobným <strong>it</strong>: <em>It's raining</em>, nikdy <em>Is raining</em>.",
            "Stupňovanie intenzity dažďa: <strong>drizzle</strong> → <strong>shower</strong> → <strong>downpour</strong>.",
            "Britská fráza „<em>lovely weather, isn't it?</em>“ nie je otázka na odpoveď — je to pozvánka do rozhovoru.",
        ],
        "related": ["cestovanie-a-letisko", "cislovky", "u-lekara"],
        "date": "2026-08-13",
    },
    {
        "slug": "cislovky",
        "title": "Anglické číslovky: čísla, dátumy a čas",
        "description": (
            "Anglické číslovky od 1 do milióna, radové číslovky, dátumy a čas. "
            "Prehľad s príkladmi a najčastejšími chybami Slovákov."
        ),
        "intro": (
            "Čísla sú v angličtine zradné práve preto, že ich považujeme za triviálne. "
            "Kým základné počítanie zvládne každý, pri dátumoch, desatinných číslach a "
            "telefónnych číslach sa chybuje takmer vždy. Tu je prehľad aj s pascami, "
            "do ktorých Slováci padajú najčastejšie."
        ),
        "words": [
            {"en": "thirteen", "sk": "trinásť", "example": "She's thirteen years old."},
            {"en": "thirty", "sk": "tridsať", "example": "It costs thirty euros."},
            {"en": "fifteen", "sk": "pätnásť", "example": "Fifteen people came."},
            {"en": "fifty", "sk": "päťdesiat", "example": "About fifty of them."},
            {"en": "hundred", "sk": "sto", "example": "Two hundred students."},
            {"en": "thousand", "sk": "tisíc", "example": "Five thousand euros."},
            {"en": "million", "sk": "milión", "example": "The city has two million people."},
            {"en": "first", "sk": "prvý", "example": "The first of May."},
            {"en": "second", "sk": "druhý", "example": "He finished second."},
            {"en": "third", "sk": "tretí", "example": "The third floor."},
            {"en": "fifth", "sk": "piaty", "example": "Her fifth birthday."},
            {"en": "twelfth", "sk": "dvanásty", "example": "The twelfth of March."},
            {"en": "half", "sk": "polovica", "example": "Half an hour."},
            {"en": "quarter", "sk": "štvrtina", "example": "A quarter past three."},
            {"en": "a couple of", "sk": "pár (dva)", "example": "A couple of days ago."},
            {"en": "a dozen", "sk": "tucet", "example": "A dozen eggs, please."},
            {"en": "once", "sk": "raz", "example": "I've been there once."},
            {"en": "twice", "sk": "dvakrát", "example": "We meet twice a week."},
            {"en": "decimal point", "sk": "desatinná čiarka", "example": "Three point five (3.5)."},
            {"en": "per cent", "sk": "percento", "example": "Twenty per cent off."},
        ],
        "tips": [
            "Klasická pasca: <strong>thirteen</strong> (13) má prízvuk na konci, <strong>thirty</strong> (30) na začiatku. V hovorenom slove je to jediný rozdiel.",
            "Angličtina používa desatinnú <strong>bodku</strong>, nie čiarku: 3.5 sa číta <em>three point five</em>. Čiarka oddeľuje tisíce (1,000).",
            "Telefónne čísla sa čítajú po jednej číslici a nula sa hovorí <em>oh</em>: 07... = <em>oh seven…</em>",
            "Po <strong>hundred</strong> a <strong>thousand</strong> sa nedáva -s, keď je pred nimi číslo: <em>two hundred</em>, nie <em>two hundreds</em>.",
        ],
        "related": ["nakupovanie", "v-hoteli", "skola"],
        "date": "2026-08-13",
    },
    {
        "slug": "telo",
        "title": "Anglické slovíčka: ľudské telo",
        "description": (
            "Anglické slovíčka o ľudskom tele — časti tela, orgány, zmysly. "
            "20 základných slov s príkladovými vetami."
        ),
        "intro": (
            "Časti tela sú základ, ktorý potrebujete u lekára, pri športe aj pri "
            "opise človeka. Väčšina slov je krátka a nepravidelná v množnom čísle — "
            "práve preto sa oplatí naučiť ich naraz a poriadne."
        ),
        "words": [
            {"en": "shoulder", "sk": "rameno", "example": "My shoulder hurts."},
            {"en": "elbow", "sk": "lakeť", "example": "He hit his elbow on the door."},
            {"en": "wrist", "sk": "zápästie", "example": "She wears a watch on her left wrist."},
            {"en": "thumb", "sk": "palec (na ruke)", "example": "I cut my thumb."},
            {"en": "chest", "sk": "hrudník", "example": "A pain in the chest."},
            {"en": "waist", "sk": "pás (driek)", "example": "The skirt is tight at the waist."},
            {"en": "hip", "sk": "bedro", "example": "She broke her hip."},
            {"en": "thigh", "sk": "stehno", "example": "Muscle pain in the thigh."},
            {"en": "knee", "sk": "koleno", "example": "He fell and hurt his knee."},
            {"en": "ankle", "sk": "členok", "example": "I twisted my ankle."},
            {"en": "heel", "sk": "päta", "example": "Blisters on my heel."},
            {"en": "eyebrow", "sk": "obočie", "example": "She raised an eyebrow."},
            {"en": "eyelash", "sk": "mihalnica", "example": "Long dark eyelashes."},
            {"en": "cheek", "sk": "líce", "example": "Tears ran down her cheeks."},
            {"en": "chin", "sk": "brada (časť tváre)", "example": "He rested his chin on his hand."},
            {"en": "throat", "sk": "hrdlo", "example": "A lump in my throat."},
            {"en": "lungs", "sk": "pľúca", "example": "Smoking damages the lungs."},
            {"en": "liver", "sk": "pečeň", "example": "Alcohol affects the liver."},
            {"en": "bone", "sk": "kosť", "example": "He broke a bone in his foot."},
            {"en": "skin", "sk": "koža", "example": "Dry skin in winter."},
        ],
        "tips": [
            "Nepravidelné množné čísla: <strong>foot → feet</strong>, <strong>tooth → teeth</strong>.",
            "Pozor: <strong>chin</strong> je brada ako časť tváre, fúzatá brada je <strong>beard</strong>.",
            "Pri častiach tela sa v angličtine používa privlastňovacie zámeno: <em>I broke my arm</em>, nie <em>the arm</em>.",
        ],
        "related": ["u-lekara", "jedlo-a-potraviny", "rodina"],
        "date": "2026-08-13",
    },
    {
        "slug": "skola",
        "title": "Anglické slovíčka: škola a vyučovanie",
        "description": (
            "Anglické slovíčka o škole — predmety, známky, skúšky, rozvrh. "
            "20 slov s vetami pre žiakov, študentov aj učiteľov."
        ),
        "intro": (
            "Školská slovná zásoba je užitočná dvakrát: potrebujú ju žiaci na hodinách "
            "angličtiny a zároveň každý, kto chce študovať alebo pracovať v zahraničí. "
            "Britský a americký školský systém sa pritom pomenúva odlišne — na to si "
            "dajte pozor najviac."
        ),
        "words": [
            {"en": "subject", "sk": "predmet", "example": "Maths is my favourite subject."},
            {"en": "timetable", "sk": "rozvrh", "example": "Check the timetable."},
            {"en": "lesson", "sk": "vyučovacia hodina", "example": "The lesson starts at eight."},
            {"en": "break", "sk": "prestávka", "example": "See you after the break."},
            {"en": "homework", "sk": "domáca úloha", "example": "Have you done your homework?"},
            {"en": "assignment", "sk": "zadanie", "example": "The assignment is due Friday."},
            {"en": "test", "sk": "písomka", "example": "We have a test tomorrow."},
            {"en": "exam", "sk": "skúška", "example": "She passed all her exams."},
            {"en": "to pass", "sk": "urobiť (skúšku)", "example": "I passed the exam."},
            {"en": "to fail", "sk": "neurobiť (prepadnúť)", "example": "He failed the test."},
            {"en": "grade / mark", "sk": "známka", "example": "She got a good mark."},
            {"en": "report card", "sk": "vysvedčenie", "example": "The report card comes in June."},
            {"en": "term", "sk": "polrok (semester)", "example": "The summer term ends in July."},
            {"en": "headteacher", "sk": "riaditeľ školy", "example": "The headteacher called a meeting."},
            {"en": "classmate", "sk": "spolužiak", "example": "My classmates helped me."},
            {"en": "to revise", "sk": "opakovať (učiť sa)", "example": "I need to revise for the test."},
            {"en": "to take notes", "sk": "robiť si poznámky", "example": "Take notes during the lecture."},
            {"en": "attendance", "sk": "dochádzka", "example": "Attendance is compulsory."},
            {"en": "degree", "sk": "vysokoškolský titul", "example": "She has a degree in biology."},
            {"en": "scholarship", "sk": "štipendium", "example": "He won a scholarship."},
        ],
        "tips": [
            "Falošný priateľ: <strong>to revise</strong> v britskej angličtine znamená „opakovať si učivo“, nie „revidovať“.",
            "<strong>Homework</strong> je nepočítateľné — nikdy <em>homeworks</em>. Jedna úloha je <em>a piece of homework</em>.",
            "Britský <strong>headteacher</strong> je americký <strong>principal</strong>; britské <strong>maths</strong> je americké <strong>math</strong>.",
        ],
        "related": ["pracovny-pohovor", "cislovky", "rodina"],
        "date": "2026-08-13",
    },
]

# Rýchly index pre routu (slug → téma).
TOPICS_BY_SLUG = {t["slug"]: t for t in TOPICS}


def get_topic(slug: str) -> dict | None:
    return TOPICS_BY_SLUG.get(slug)


def related_topics(topic: dict) -> list[dict]:
    """Príbuzné témy ako plné záznamy (neexistujúce slugy ticho vynechá)."""
    return [TOPICS_BY_SLUG[s] for s in topic.get("related", []) if s in TOPICS_BY_SLUG]
