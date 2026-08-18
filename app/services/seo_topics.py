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
    {
        "slug": "sport-a-fitness",
        "title": "Anglické slovíčka: šport a fitness",
        "description": (
            "Anglické slovíčka o športe a fitness — posilňovňa, tréning, zápas, "
            "zranenia. 18 slov s vetami, ktoré naozaj počuješ."
        ),
        "intro": (
            "Šport je vďačná téma na konverzáciu — funguje ako prvá otázka pri "
            "zoznámení aj ako bezpečná téma v práci. Problém býva v tom, že "
            "učebnice učia „to do sport“, kým rodení hovoriaci povedia „to play "
            "football“ alebo „to go running“. Nižšie nájdeš slová aj s väzbami, "
            "v ktorých sa naozaj používajú."
        ),
        "words": [
            {"en": "gym", "sk": "posilňovňa", "example": "I go to the gym twice a week."},
            {"en": "workout", "sk": "tréning (cvičenie)", "example": "That was a tough workout."},
            {"en": "to work out", "sk": "cvičiť", "example": "She works out every morning."},
            {"en": "warm-up", "sk": "rozcvička", "example": "Never skip the warm-up."},
            {"en": "to stretch", "sk": "naťahovať sa", "example": "Stretch before you run."},
            {"en": "match", "sk": "zápas", "example": "The match starts at eight."},
            {"en": "team", "sk": "tím", "example": "Which team do you support?"},
            {"en": "coach", "sk": "tréner", "example": "The coach changed the tactics."},
            {"en": "score", "sk": "skóre", "example": "What was the final score?"},
            {"en": "to win", "sk": "vyhrať", "example": "We won three to one."},
            {"en": "to lose", "sk": "prehrať", "example": "They lost the final."},
            {"en": "draw", "sk": "remíza", "example": "The game ended in a draw."},
            {"en": "referee", "sk": "rozhodca", "example": "The referee gave a penalty."},
            {"en": "injury", "sk": "zranenie", "example": "He is out with a knee injury."},
            {"en": "to train", "sk": "trénovať", "example": "They train five times a week."},
            {"en": "fitness", "sk": "kondícia", "example": "My fitness has improved a lot."},
            {"en": "treadmill", "sk": "bežecký pás", "example": "I ran ten kilometres on the treadmill."},
            {"en": "weights", "sk": "činky", "example": "He lifts weights after work."},
        ],
        "tips": [
            "Loptové hry idú s <strong>play</strong> (<em>play football, play tennis</em>), aktivity zakončené na -ing s <strong>go</strong> (<em>go running, go swimming</em>) a cvičenia v posilňovni s <strong>do</strong> (<em>do push-ups</em>).",
            "Britský <strong>football</strong> je americký <strong>soccer</strong> — v USA je <em>football</em> americký futbal.",
            "Skóre sa číta „three to one“ alebo „three one“, nikdy nie <em>three per one</em>.",
        ],
        "related": ["telo", "volny-cas-a-konicky", "cislovky"],
        "date": "2026-08-18",
    },
    {
        "slug": "v-meste-a-doprava",
        "title": "Anglické slovíčka: v meste a doprava",
        "description": (
            "Anglické slovíčka na orientáciu v meste — MHD, lístky, smer cesty, "
            "parkovanie. 18 slov s vetami, ktoré sa hodia hneď."
        ),
        "intro": (
            "Opýtať sa na cestu je jedna z mála situácií, kde odpoveď musíš "
            "naozaj pochopiť — inak skončíš inde. Pomôže poznať pár slov o smere "
            "a názvy dopravných prostriedkov, ktoré sa v britskej a americkej "
            "angličtine líšia. Každé slovo nižšie má vetu, akú počuješ na ulici "
            "alebo v aplikácii na cestovanie."
        ),
        "words": [
            {"en": "underground", "sk": "metro (UK)", "example": "Take the underground to the centre."},
            {"en": "subway", "sk": "metro (US)", "example": "The subway runs all night."},
            {"en": "bus stop", "sk": "zastávka autobusu", "example": "I'll wait at the bus stop."},
            {"en": "single ticket", "sk": "jednosmerný lístok", "example": "One single ticket, please."},
            {"en": "return ticket", "sk": "spiatočný lístok", "example": "A return ticket is cheaper."},
            {"en": "platform", "sk": "nástupište", "example": "The train leaves from platform four."},
            {"en": "to change", "sk": "prestupovať", "example": "You have to change at the next station."},
            {"en": "crossroads", "sk": "križovatka", "example": "Turn left at the crossroads."},
            {"en": "traffic lights", "sk": "semafor", "example": "Stop at the traffic lights."},
            {"en": "pedestrian crossing", "sk": "priechod pre chodcov", "example": "Use the pedestrian crossing."},
            {"en": "roundabout", "sk": "kruhový objazd", "example": "Take the second exit at the roundabout."},
            {"en": "straight ahead", "sk": "rovno", "example": "Go straight ahead for two blocks."},
            {"en": "to get off", "sk": "vystúpiť", "example": "Get off at the third stop."},
            {"en": "traffic jam", "sk": "dopravná zápcha", "example": "We were stuck in a traffic jam."},
            {"en": "car park", "sk": "parkovisko (UK)", "example": "The car park is full."},
            {"en": "fare", "sk": "cestovné", "example": "The fare is two pounds fifty."},
            {"en": "timetable", "sk": "cestovný poriadok", "example": "Check the timetable online."},
            {"en": "to be delayed", "sk": "meškať", "example": "The bus is delayed by ten minutes."},
        ],
        "tips": [
            "Britská <strong>underground</strong> (v Londýne aj <em>the Tube</em>) je americká <strong>subway</strong>; americká <em>subway</em> v Británii znamená podchod.",
            "V dopravných prostriedkoch sa jazdí <strong>by bus, by train, by car</strong> — bez člena. Ale „in the car“, keď myslíš konkrétne auto.",
            "Britský <strong>car park</strong> je americký <strong>parking lot</strong>, britský <strong>petrol</strong> americký <strong>gas</strong>.",
        ],
        "related": ["cestovanie-a-letisko", "v-hoteli", "nakupovanie"],
        "date": "2026-08-18",
    },
    {
        "slug": "byvanie-a-domacnost",
        "title": "Anglické slovíčka: bývanie a domácnosť",
        "description": (
            "Anglické slovíčka o bývaní — miestnosti, nábytok, nájom, opravy. "
            "18 slov s vetami na prenájom bytu aj bežný deň doma."
        ),
        "intro": (
            "Slovná zásoba o bývaní sa zíde dvakrát: keď hľadáš ubytovanie v "
            "zahraničí a keď rozprávaš o tom, ako bývaš doma. Inzeráty na byty "
            "sú navyše plné skratiek a slov, ktoré v učebnici nenájdeš. Nižšie "
            "sú tie najbežnejšie, vždy s vetou v prirodzenom kontexte."
        ),
        "words": [
            {"en": "flat", "sk": "byt (UK)", "example": "We rent a flat near the park."},
            {"en": "apartment", "sk": "byt (US)", "example": "Their apartment is on the fifth floor."},
            {"en": "landlord", "sk": "prenajímateľ", "example": "The landlord raised the rent."},
            {"en": "tenant", "sk": "nájomník", "example": "The tenant moved out last week."},
            {"en": "rent", "sk": "nájomné", "example": "The rent is due on the first."},
            {"en": "deposit", "sk": "kaucia", "example": "You get the deposit back at the end."},
            {"en": "ground floor", "sk": "prízemie", "example": "The kitchen is on the ground floor."},
            {"en": "bills", "sk": "poplatky za energie", "example": "Are the bills included?"},
            {"en": "furnished", "sk": "zariadený", "example": "We are looking for a furnished flat."},
            {"en": "washing machine", "sk": "práčka", "example": "The washing machine is broken."},
            {"en": "fridge", "sk": "chladnička", "example": "Put the milk in the fridge."},
            {"en": "cupboard", "sk": "skrinka", "example": "The plates are in the cupboard."},
            {"en": "tap", "sk": "vodovodný kohútik", "example": "The tap is dripping."},
            {"en": "to do the dishes", "sk": "umývať riad", "example": "Whose turn is it to do the dishes?"},
            {"en": "to take out the rubbish", "sk": "vyniesť smeti", "example": "Could you take out the rubbish?"},
            {"en": "hoover", "sk": "vysávač (UK)", "example": "The hoover is in the hallway."},
            {"en": "neighbour", "sk": "sused", "example": "Our neighbours are very quiet."},
            {"en": "to move in", "sk": "nasťahovať sa", "example": "They moved in last month."},
        ],
        "tips": [
            "Britské poschodia sú posunuté: <strong>ground floor</strong> je prízemie, <strong>first floor</strong> je naše prvé poschodie. V USA je <em>first floor</em> prízemie.",
            "<strong>Rent</strong> je nájomné aj sloveso „prenajať si“; „prenajať niekomu“ je <strong>to rent out</strong> alebo <strong>to let</strong> (odtiaľ nápis <em>To Let</em>).",
            "Britský <strong>hoover</strong> a <strong>rubbish</strong> sú americké <strong>vacuum cleaner</strong> a <strong>trash</strong>.",
        ],
        "related": ["nakupovanie", "rodina", "v-hoteli"],
        "date": "2026-08-18",
    },
    {
        "slug": "pocitac-a-internet",
        "title": "Anglické slovíčka: počítač a internet",
        "description": (
            "Anglické slovíčka o počítači a internete — účty, heslá, súbory, "
            "poruchy. 18 slov s vetami z bežnej práce s technikou."
        ),
        "intro": (
            "Väčšina rozhraní je po anglicky, takže tieto slová vidíš denne aj "
            "bez toho, aby si sa ich učil. Problém nastane, keď treba niečo "
            "opísať alebo požiadať o pomoc — vtedy sa hodí vedieť, že „prihlásiť "
            "sa“ je <em>log in</em> a nie <em>login</em>. Nižšie sú slová aj s "
            "väzbami, ktoré sa najčastejšie mýlia."
        ),
        "words": [
            {"en": "account", "sk": "účet", "example": "Create an account to continue."},
            {"en": "password", "sk": "heslo", "example": "I forgot my password again."},
            {"en": "to log in", "sk": "prihlásiť sa", "example": "Log in with your email address."},
            {"en": "to sign up", "sk": "zaregistrovať sa", "example": "Sign up for a free trial."},
            {"en": "settings", "sk": "nastavenia", "example": "You can change it in the settings."},
            {"en": "file", "sk": "súbor", "example": "Send me the file by email."},
            {"en": "folder", "sk": "priečinok", "example": "Save it in the shared folder."},
            {"en": "to download", "sk": "stiahnuť", "example": "Download the app from the store."},
            {"en": "to upload", "sk": "nahrať", "example": "Upload your photo here."},
            {"en": "screen", "sk": "obrazovka", "example": "My screen went black."},
            {"en": "screenshot", "sk": "snímka obrazovky", "example": "Send me a screenshot of the error."},
            {"en": "browser", "sk": "prehliadač", "example": "Try a different browser."},
            {"en": "link", "sk": "odkaz", "example": "Click the link in the email."},
            {"en": "to update", "sk": "aktualizovať", "example": "Update the app to the latest version."},
            {"en": "to crash", "sk": "spadnúť (zlyhať)", "example": "The program crashed twice today."},
            {"en": "to back up", "sk": "zálohovať", "example": "Back up your data every week."},
            {"en": "device", "sk": "zariadenie", "example": "You can use it on any device."},
            {"en": "charger", "sk": "nabíjačka", "example": "I left my charger at home."},
        ],
        "tips": [
            "Sloveso je <strong>to log in</strong> (dve slová), podstatné meno <strong>login</strong> (jedno). To isté platí pre <em>set up</em> / <em>setup</em> a <em>back up</em> / <em>backup</em>.",
            "<strong>Software</strong> aj <strong>hardware</strong> sú nepočítateľné — nikdy <em>softwares</em>. Jeden program je <em>a piece of software</em>.",
            "Pri probléme je najprirodzenejšie „It doesn't work“ alebo „It's not working“ — nie <em>It doesn't function</em>.",
        ],
        "related": ["praca-a-kancelaria", "telefonovanie-a-emaily", "pracovny-pohovor"],
        "date": "2026-08-18",
    },
    {
        "slug": "peniaze-a-banka",
        "title": "Anglické slovíčka: peniaze a banka",
        "description": (
            "Anglické slovíčka o peniazoch — banka, platby, účty, sporenie. "
            "18 slov s vetami z bankomatu, obchodu aj rozhovoru o financiách."
        ),
        "intro": (
            "Pri peniazoch sa oplatí rozumieť presne — rozdiel medzi <em>fee</em> "
            "a <em>fine</em> je pár písmen, ale v praxi poplatok verzus pokuta. "
            "Táto sada pokrýva slová, ktoré uvidíš na bankomate, v internet "
            "bankingu aj na účtenke, vždy s vetou v bežnej situácii."
        ),
        "words": [
            {"en": "bank account", "sk": "bankový účet", "example": "I opened a bank account online."},
            {"en": "cash", "sk": "hotovosť", "example": "Can I pay in cash?"},
            {"en": "card", "sk": "karta", "example": "Card or cash?"},
            {"en": "to withdraw", "sk": "vybrať (peniaze)", "example": "I need to withdraw some money."},
            {"en": "to transfer", "sk": "previesť", "example": "I'll transfer the money tomorrow."},
            {"en": "balance", "sk": "zostatok", "example": "Check your balance first."},
            {"en": "fee", "sk": "poplatok", "example": "There is no monthly fee."},
            {"en": "fine", "sk": "pokuta", "example": "He paid a fine for parking."},
            {"en": "interest", "sk": "úrok", "example": "The interest rate went up."},
            {"en": "loan", "sk": "pôžička", "example": "They took out a loan for the car."},
            {"en": "mortgage", "sk": "hypotéka", "example": "We are still paying off the mortgage."},
            {"en": "savings", "sk": "úspory", "example": "She put her savings in a fixed account."},
            {"en": "to afford", "sk": "dovoliť si (finančne)", "example": "I can't afford a new laptop."},
            {"en": "invoice", "sk": "faktúra", "example": "The invoice is due in 14 days."},
            {"en": "receipt", "sk": "účtenka", "example": "Keep the receipt, just in case."},
            {"en": "expenses", "sk": "výdavky", "example": "Travel expenses are covered."},
            {"en": "salary", "sk": "plat", "example": "The salary is paid monthly."},
            {"en": "to save up", "sk": "šetriť si", "example": "We are saving up for a holiday."},
        ],
        "tips": [
            "<strong>Money</strong> je nepočítateľné: <em>How much money</em>, nikdy <em>how many moneys</em>.",
            "<strong>To afford</strong> chodí takmer vždy s <em>can / can't</em> — „I can't afford it“, nie <em>I don't afford it</em>.",
            "Britská výslovnosť <strong>receipt</strong> je /rɪˈsiːt/ — písmeno „p“ sa nečíta.",
        ],
        "related": ["nakupovanie", "praca-a-kancelaria", "cislovky"],
        "date": "2026-08-18",
    },
    {
        "slug": "praca-a-kancelaria",
        "title": "Anglické slovíčka: práca a kancelária",
        "description": (
            "Anglické slovíčka do práce — porady, termíny, kolegovia, "
            "dovolenka. 18 slov s vetami z bežného pracovného dňa."
        ),
        "intro": (
            "V práci sa najviac opakuje pár desiatok slov — porada, termín, "
            "úloha, dovolenka. Keď ich máš isté, pracovná angličtina prestane "
            "byť stres, aj keď gramatika nie je dokonalá. Vety nižšie sú tie, "
            "ktoré počuješ na hovoroch a čítaš v e-mailoch."
        ),
        "words": [
            {"en": "meeting", "sk": "porada", "example": "The meeting starts at nine."},
            {"en": "deadline", "sk": "termín (uzávierka)", "example": "The deadline is Friday."},
            {"en": "task", "sk": "úloha", "example": "I have three tasks left."},
            {"en": "colleague", "sk": "kolega", "example": "A colleague of mine speaks Spanish."},
            {"en": "boss", "sk": "šéf", "example": "My boss is on holiday this week."},
            {"en": "staff", "sk": "personál (zamestnanci)", "example": "The staff are very helpful."},
            {"en": "shift", "sk": "zmena (pracovná)", "example": "I work the night shift."},
            {"en": "overtime", "sk": "nadčas", "example": "She worked overtime again."},
            {"en": "day off", "sk": "voľný deň", "example": "I'm taking a day off on Monday."},
            {"en": "holiday", "sk": "dovolenka (UK)", "example": "He is on holiday until June."},
            {"en": "sick leave", "sk": "práceneschopnosť", "example": "He is on sick leave."},
            {"en": "to apply for", "sk": "uchádzať sa o", "example": "I applied for a new position."},
            {"en": "to hire", "sk": "prijať (do práce)", "example": "They hired two new developers."},
            {"en": "to resign", "sk": "dať výpoveď", "example": "She resigned after five years."},
            {"en": "notice period", "sk": "výpovedná lehota", "example": "My notice period is two months."},
            {"en": "report", "sk": "správa (report)", "example": "I sent the report yesterday."},
            {"en": "to be in charge of", "sk": "mať na starosti", "example": "She is in charge of marketing."},
            {"en": "workload", "sk": "pracovné zaťaženie", "example": "My workload is heavy this month."},
        ],
        "tips": [
            "<strong>Staff</strong> je hromadné podstatné meno — v britskej angličtine s množným slovesom: <em>The staff are…</em>. Jeden človek je <em>a member of staff</em>.",
            "Britská <strong>holiday</strong> je americká <strong>vacation</strong>; americký <em>holiday</em> je sviatok.",
            "Píše sa <strong>to apply for a job</strong> (nie <em>apply to</em>) a <strong>to be responsible for</strong>.",
        ],
        "related": ["pracovny-pohovor", "telefonovanie-a-emaily", "pocitac-a-internet"],
        "date": "2026-08-18",
    },
    {
        "slug": "oblecenie-a-moda",
        "title": "Anglické slovíčka: oblečenie a móda",
        "description": (
            "Anglické slovíčka o oblečení — kúsky šatníka, veľkosti, skúšanie, "
            "reklamácie. 18 slov s vetami priamo z obchodu."
        ),
        "intro": (
            "Nakupovanie oblečenia je situácia, kde stačí pár presných slov: "
            "veľkosť, skúšobná kabínka, výmena. Navyše sa tu skrýva niekoľko "
            "slov, ktoré v britskej a americkej angličtine znamenajú niečo iné "
            "— <em>pants</em> je asi najznámejší prípad. Nižšie nájdeš tie "
            "najpoužívanejšie aj s vetami."
        ),
        "words": [
            {"en": "clothes", "sk": "oblečenie", "example": "I need to buy some new clothes."},
            {"en": "trousers", "sk": "nohavice (UK)", "example": "These trousers are too tight."},
            {"en": "shirt", "sk": "košeľa", "example": "He wore a white shirt."},
            {"en": "jumper", "sk": "sveter (UK)", "example": "Take a jumper, it's cold."},
            {"en": "jacket", "sk": "bunda", "example": "My jacket is waterproof."},
            {"en": "dress", "sk": "šaty", "example": "She bought a summer dress."},
            {"en": "trainers", "sk": "tenisky (UK)", "example": "I run in old trainers."},
            {"en": "size", "sk": "veľkosť", "example": "Do you have this in size 40?"},
            {"en": "to try on", "sk": "vyskúšať si", "example": "Can I try these on?"},
            {"en": "fitting room", "sk": "skúšobná kabínka", "example": "The fitting rooms are upstairs."},
            {"en": "to fit", "sk": "sedieť (veľkosťou)", "example": "These jeans don't fit me."},
            {"en": "to suit", "sk": "pristať (sluší)", "example": "That colour really suits you."},
            {"en": "tight", "sk": "tesný", "example": "The shoes are a bit tight."},
            {"en": "loose", "sk": "voľný", "example": "I prefer a loose fit."},
            {"en": "to wear", "sk": "mať na sebe", "example": "What are you wearing tonight?"},
            {"en": "to get changed", "sk": "prezliecť sa", "example": "I'll get changed after work."},
            {"en": "receipt", "sk": "účtenka", "example": "You need the receipt to exchange it."},
            {"en": "to exchange", "sk": "vymeniť", "example": "Can I exchange this for a larger size?"},
        ],
        "tips": [
            "Britské <strong>pants</strong> sú spodky, americké <strong>pants</strong> sú nohavice. V Británii povedz radšej <em>trousers</em>.",
            "<strong>Clothes</strong> je vždy v množnom čísle — nikdy <em>a clothes</em>. Jeden kus je <em>an item of clothing</em>.",
            "Rozdiel: <strong>to fit</strong> je o veľkosti, <strong>to suit</strong> o tom, či ti to pristane, <strong>to match</strong> o tom, či to ladí s ostatným.",
        ],
        "related": ["nakupovanie", "farby-a-tvary", "telo"],
        "date": "2026-08-18",
    },
    {
        "slug": "zvierata",
        "title": "Anglické slovíčka: zvieratá",
        "description": (
            "Anglické slovíčka o zvieratách — domáce, hospodárske aj divé. "
            "18 slov s vetami, ktoré sa hodia deťom aj dospelým."
        ),
        "intro": (
            "Zvieratá patria k prvým slovám, ktoré sa deti učia — a k tým, čo "
            "dospelí potrebujú pri rozhovore o domácom miláčikovi alebo na "
            "výlete. Angličtina navyše rozlišuje zviera a mäso z neho "
            "(<em>cow</em> verzus <em>beef</em>), čo pri jedálnom lístku "
            "prekvapí. Nižšie sú najbežnejšie druhy s vetami."
        ),
        "words": [
            {"en": "pet", "sk": "domáci miláčik", "example": "Do you have any pets?"},
            {"en": "dog", "sk": "pes", "example": "Our dog sleeps in the kitchen."},
            {"en": "cat", "sk": "mačka", "example": "The cat is on the roof again."},
            {"en": "puppy", "sk": "šteňa", "example": "They got a puppy last week."},
            {"en": "kitten", "sk": "mačiatko", "example": "The kitten is only six weeks old."},
            {"en": "horse", "sk": "kôň", "example": "She rides a horse every Sunday."},
            {"en": "cow", "sk": "krava", "example": "The cows are in the field."},
            {"en": "sheep", "sk": "ovca", "example": "There were sheep everywhere."},
            {"en": "pig", "sk": "prasa", "example": "The pigs live behind the barn."},
            {"en": "chicken", "sk": "sliepka (kura)", "example": "We keep six chickens."},
            {"en": "bird", "sk": "vták", "example": "A bird was singing outside."},
            {"en": "fish", "sk": "ryba", "example": "The fish in this lake are huge."},
            {"en": "mouse", "sk": "myš", "example": "There is a mouse in the garage."},
            {"en": "bear", "sk": "medveď", "example": "Bears live in these mountains."},
            {"en": "fox", "sk": "líška", "example": "A fox crossed the road."},
            {"en": "wild", "sk": "divoký", "example": "These are wild animals, not pets."},
            {"en": "to feed", "sk": "kŕmiť", "example": "Don't feed the animals."},
            {"en": "to bark", "sk": "brechať", "example": "The dog barks at everyone."},
        ],
        "tips": [
            "Nepravidelné množné čísla: <strong>mouse → mice</strong>, <strong>goose → geese</strong>; <strong>sheep</strong>, <strong>fish</strong> a <strong>deer</strong> majú tvar rovnaký.",
            "Zviera verzus mäso: <em>cow → beef</em>, <em>pig → pork</em>, <em>sheep → mutton</em>, <em>calf → veal</em>. Pri <em>chicken</em> a <em>fish</em> je slovo rovnaké.",
            "O zvieratách sa hovorí <strong>it</strong>, pokiaľ nejde o vlastného miláčika — vtedy je prirodzené <em>he</em> alebo <em>she</em>.",
        ],
        "related": ["priroda-a-zivotne-prostredie", "jedlo-a-potraviny", "rodina"],
        "date": "2026-08-18",
    },
    {
        "slug": "priroda-a-zivotne-prostredie",
        "title": "Anglické slovíčka: príroda a životné prostredie",
        "description": (
            "Anglické slovíčka o prírode a ekológii — krajina, triedenie odpadu, "
            "klíma. 18 slov s vetami do školy aj na diskusiu."
        ),
        "intro": (
            "Životné prostredie je téma, ktorá sa objaví na maturite, na "
            "jazykovej skúške aj v bežnom rozhovore o počasí. Väčšina slov je "
            "medzinárodná, ale niekoľko sa pravidelne pletie — napríklad "
            "<em>climate</em> verzus <em>weather</em>. Nižšie sú slová aj s "
            "vetami, v ktorých znejú prirodzene."
        ),
        "words": [
            {"en": "nature", "sk": "príroda", "example": "We spent the weekend in nature."},
            {"en": "forest", "sk": "les", "example": "The forest starts behind the village."},
            {"en": "mountain", "sk": "hora", "example": "They climbed the highest mountain."},
            {"en": "river", "sk": "rieka", "example": "The river was very low this summer."},
            {"en": "lake", "sk": "jazero", "example": "We swam in the lake."},
            {"en": "field", "sk": "pole (lúka)", "example": "The field is full of flowers."},
            {"en": "climate", "sk": "podnebie", "example": "The climate is changing fast."},
            {"en": "climate change", "sk": "klimatická zmena", "example": "Climate change affects everyone."},
            {"en": "pollution", "sk": "znečistenie", "example": "Air pollution is worse in winter."},
            {"en": "waste", "sk": "odpad", "example": "We produce too much waste."},
            {"en": "to recycle", "sk": "recyklovať", "example": "We recycle paper and glass."},
            {"en": "rubbish bin", "sk": "kôš na odpad (UK)", "example": "Put it in the rubbish bin."},
            {"en": "renewable", "sk": "obnoviteľný", "example": "Renewable energy is getting cheaper."},
            {"en": "to save energy", "sk": "šetriť energiu", "example": "Turn off the lights to save energy."},
            {"en": "endangered", "sk": "ohrozený (druh)", "example": "This species is endangered."},
            {"en": "to protect", "sk": "chrániť", "example": "We must protect the forests."},
            {"en": "drought", "sk": "sucho", "example": "The drought lasted three months."},
            {"en": "flood", "sk": "povodeň", "example": "The floods damaged the bridge."},
        ],
        "tips": [
            "<strong>Weather</strong> je počasie dnes, <strong>climate</strong> je dlhodobé podnebie — na skúške sa toto rozlíšenie oceňuje.",
            "<strong>Nature</strong> v zmysle prírody ide bez člena: <em>in nature</em>, nie <em>in the nature</em>.",
            "Britský <strong>rubbish</strong> je americký <strong>garbage</strong> alebo <strong>trash</strong>; kôš je <em>bin</em> verzus <em>trash can</em>.",
        ],
        "related": ["pocasie", "zvierata", "volny-cas-a-konicky"],
        "date": "2026-08-18",
    },
    {
        "slug": "volny-cas-a-konicky",
        "title": "Anglické slovíčka: voľný čas a koníčky",
        "description": (
            "Anglické slovíčka o koníčkoch — čítanie, hudba, filmy, výlety. "
            "18 slov s vetami na otázku „What do you do in your free time?“."
        ),
        "intro": (
            "„What do you do in your free time?“ je otázka, ktorá príde v každom "
            "prvom rozhovore aj na jazykovej skúške. Odpovedať dvoma slovami je "
            "škoda — stačí pár väzieb a hneď máš plnohodnotnú vetu. Nižšie sú "
            "slová aj s tvarmi, v ktorých sa naozaj používajú."
        ),
        "words": [
            {"en": "hobby", "sk": "koníček", "example": "Photography is my main hobby."},
            {"en": "free time", "sk": "voľný čas", "example": "I don't have much free time."},
            {"en": "to be into", "sk": "zaujímať sa o", "example": "I'm really into board games."},
            {"en": "to hang out", "sk": "tráviť čas (s niekým)", "example": "We hang out at weekends."},
            {"en": "to go out", "sk": "ísť von (zabávať sa)", "example": "We went out on Friday night."},
            {"en": "reading", "sk": "čítanie", "example": "Reading helps me relax."},
            {"en": "novel", "sk": "román", "example": "I'm reading a crime novel."},
            {"en": "to draw", "sk": "kresliť", "example": "She draws every evening."},
            {"en": "to play an instrument", "sk": "hrať na nástroj", "example": "Do you play an instrument?"},
            {"en": "gig", "sk": "koncert (menší)", "example": "We went to a gig last night."},
            {"en": "to watch a series", "sk": "pozerať seriál", "example": "I watch a series before bed."},
            {"en": "board game", "sk": "spoločenská hra", "example": "Board games are back in fashion."},
            {"en": "hiking", "sk": "turistika", "example": "Hiking is popular here."},
            {"en": "cycling", "sk": "cyklistika", "example": "Cycling to work saves money."},
            {"en": "to bake", "sk": "piecť", "example": "He bakes bread at weekends."},
            {"en": "to travel", "sk": "cestovať", "example": "They travel whenever they can."},
            {"en": "to relax", "sk": "oddychovať", "example": "I relax by walking the dog."},
            {"en": "to look forward to", "sk": "tešiť sa na", "example": "I'm looking forward to the weekend."},
        ],
        "tips": [
            "Po <strong>look forward to</strong> ide -ingový tvar: <em>I'm looking forward to seeing you</em>, nie <em>to see</em>.",
            "Pri koníčkoch sa najprirodzenejšie hovorí „I like <strong>reading</strong>“ (-ing), nie <em>I like to read</em> — to znie ako jednorazový zámer.",
            "<strong>To be into something</strong> je hovorové „baviť ma niečo“ a v konverzácii znie prirodzenejšie než <em>my hobby is…</em>.",
        ],
        "related": ["sport-a-fitness", "cas-a-datumy", "priroda-a-zivotne-prostredie"],
        "date": "2026-08-18",
    },
    {
        "slug": "cas-a-datumy",
        "title": "Anglické slovíčka: čas a dátumy",
        "description": (
            "Anglické slovíčka o čase — hodiny, dni, mesiace, dohodnutie "
            "stretnutia. 18 slov s vetami a pravidlami na predložky."
        ),
        "intro": (
            "Čas je téma, kde nestačí poznať slová — treba aj predložky. "
            "<em>At</em> ide s hodinou, <em>on</em> s dňom a <em>in</em> s "
            "mesiacom či rokom, a práve na tomto sa najčastejšie chybuje. "
            "Nižšie nájdeš slová aj vety, na ktorých si pravidlo zapamätáš "
            "prirodzene."
        ),
        "words": [
            {"en": "o'clock", "sk": "hodín (celá hodina)", "example": "The train leaves at six o'clock."},
            {"en": "half past", "sk": "pol (po hodine)", "example": "It's half past seven."},
            {"en": "quarter to", "sk": "trištvrte na", "example": "We met at a quarter to nine."},
            {"en": "midnight", "sk": "polnoc", "example": "The shop closes at midnight."},
            {"en": "noon", "sk": "poludnie", "example": "Let's meet at noon."},
            {"en": "weekday", "sk": "všedný deň", "example": "I work on weekdays only."},
            {"en": "weekend", "sk": "víkend", "example": "See you at the weekend."},
            {"en": "fortnight", "sk": "dva týždne (UK)", "example": "I'll be back in a fortnight."},
            {"en": "the day after tomorrow", "sk": "pozajtra", "example": "The exam is the day after tomorrow."},
            {"en": "the day before yesterday", "sk": "predvčerom", "example": "We arrived the day before yesterday."},
            {"en": "deadline", "sk": "termín", "example": "The deadline is the end of May."},
            {"en": "appointment", "sk": "dohodnutá schôdzka", "example": "I have an appointment at four."},
            {"en": "to be on time", "sk": "byť načas", "example": "She is always on time."},
            {"en": "to be late", "sk": "meškať", "example": "Sorry I'm late."},
            {"en": "early", "sk": "skoro (zavčasu)", "example": "We arrived twenty minutes early."},
            {"en": "to postpone", "sk": "odložiť", "example": "They postponed the meeting."},
            {"en": "to last", "sk": "trvať", "example": "The film lasts two hours."},
            {"en": "so far", "sk": "doteraz", "example": "So far everything is fine."},
        ],
        "tips": [
            "Predložky: <strong>at</strong> + hodina (<em>at six</em>), <strong>on</strong> + deň a dátum (<em>on Monday, on 5 May</em>), <strong>in</strong> + mesiac, rok, ročné obdobie (<em>in July, in 2026</em>).",
            "Britský dátum je <strong>5 May 2026</strong> (deň-mesiac), americký <strong>May 5, 2026</strong> (mesiac-deň) — pri číselnom zápise 5/6 preto Brit číta 5. jún a Američan 6. máj.",
            "Britské „at the weekend“ je americké „on the weekend“. Obe sú správne, len na inom kontinente.",
        ],
        "related": ["cislovky", "praca-a-kancelaria", "cestovanie-a-letisko"],
        "date": "2026-08-18",
    },
    {
        "slug": "emocie-a-pocity",
        "title": "Anglické slovíčka: emócie a pocity",
        "description": (
            "Anglické slovíčka o pocitoch — od nervozity po úľavu. 18 slov "
            "s vetami, aby si vedel povedať viac než „I'm fine“."
        ),
        "intro": (
            "Väčšina učebníc skončí pri <em>happy</em> a <em>sad</em>, lenže "
            "v skutočnom rozhovore potrebuješ odtiene: nervózny pred pohovorom, "
            "sklamaný z výsledku, uľavený, keď je po ňom. Nižšie sú slová, "
            "ktoré rozdiel spravia, vždy aj s vetou v situácii, kde ich počuješ."
        ),
        "words": [
            {"en": "happy", "sk": "šťastný", "example": "I'm happy with the result."},
            {"en": "glad", "sk": "rád (potešený)", "example": "I'm glad you came."},
            {"en": "excited", "sk": "natešený", "example": "She is excited about the trip."},
            {"en": "nervous", "sk": "nervózny", "example": "I'm nervous about the interview."},
            {"en": "worried", "sk": "ustarostený", "example": "He looked worried."},
            {"en": "scared", "sk": "vystrašený", "example": "The dog is scared of storms."},
            {"en": "angry", "sk": "nahnevaný", "example": "Don't be angry with me."},
            {"en": "annoyed", "sk": "otrávený (podráždený)", "example": "I was annoyed by the noise."},
            {"en": "upset", "sk": "rozrušený", "example": "She was upset about the news."},
            {"en": "disappointed", "sk": "sklamaný", "example": "We were disappointed with the film."},
            {"en": "relieved", "sk": "uľavený", "example": "I was relieved when it was over."},
            {"en": "proud", "sk": "hrdý", "example": "His parents are proud of him."},
            {"en": "confused", "sk": "zmätený", "example": "I'm confused by these instructions."},
            {"en": "tired", "sk": "unavený", "example": "I'm too tired to cook."},
            {"en": "bored", "sk": "znudený", "example": "The children were bored."},
            {"en": "lonely", "sk": "osamelý", "example": "He felt lonely in the new city."},
            {"en": "grateful", "sk": "vďačný", "example": "I'm grateful for your help."},
            {"en": "to cheer up", "sk": "rozveseliť (sa)", "example": "Cheer up, it's not that bad."},
        ],
        "tips": [
            "Koncovka rozhoduje: <strong>bored</strong> je „nudím sa“, <strong>boring</strong> je „nudný“. To isté platí pre <em>interested / interesting</em> a <em>confused / confusing</em>.",
            "Predložky treba brať ako súčasť slova: <em>angry <strong>with</strong> someone</em>, <em>angry <strong>about</strong> something</em>, <em>proud <strong>of</strong></em>, <em>worried <strong>about</strong></em>.",
            "<strong>Nervous</strong> je nervózny, nie „nervný“ — a <em>sympathetic</em> neznamená sympatický, ale súcitný.",
        ],
        "related": ["rodina", "u-lekara", "pracovny-pohovor"],
        "date": "2026-08-18",
    },
    {
        "slug": "telefonovanie-a-emaily",
        "title": "Anglické slovíčka: telefonovanie a e-maily",
        "description": (
            "Anglické frázy na telefonovanie a písanie e-mailov — oslovenia, "
            "žiadosti, záver. 18 výrazov s vetami, ktoré môžeš použiť hneď."
        ),
        "intro": (
            "Telefonát v cudzom jazyku je ťažší než rozhovor naživo — chýba "
            "reč tela a často aj kvalita zvuku. Pomôže mať pripravených pár "
            "hotových fráz na začiatok, na požiadanie o zopakovanie a na "
            "rozlúčku. To isté platí pre e-maily, kde stačí poznať správne "
            "oslovenie a záver."
        ),
        "words": [
            {"en": "Speaking.", "sk": "Pri telefóne. (to som ja)", "example": "\"Is that Anna?\" \"Speaking.\""},
            {"en": "to call back", "sk": "zavolať späť", "example": "Can I call you back in ten minutes?"},
            {"en": "to hold on", "sk": "počkať (na linke)", "example": "Hold on, I'll check."},
            {"en": "to put through", "sk": "prepojiť", "example": "I'll put you through to sales."},
            {"en": "voicemail", "sk": "odkazová schránka", "example": "Leave a message on my voicemail."},
            {"en": "to hang up", "sk": "zavesiť", "example": "Don't hang up yet."},
            {"en": "Could you repeat that?", "sk": "Môžete to zopakovať?", "example": "Sorry, could you repeat that?"},
            {"en": "You're breaking up.", "sk": "Seká sa mi to.", "example": "Sorry, you're breaking up."},
            {"en": "Dear Sir or Madam", "sk": "Vážený pán/pani (neznámy adresát)", "example": "Dear Sir or Madam, I am writing to ask…"},
            {"en": "Hi / Hello", "sk": "Ahoj/Dobrý deň (bežný e-mail)", "example": "Hi Tom, thanks for the update."},
            {"en": "I am writing to…", "sk": "Píšem vám ohľadom…", "example": "I am writing to confirm our meeting."},
            {"en": "Please find attached", "sk": "V prílohe posielam", "example": "Please find attached the invoice."},
            {"en": "attachment", "sk": "príloha", "example": "The attachment didn't arrive."},
            {"en": "to reply", "sk": "odpovedať", "example": "I'll reply by Friday."},
            {"en": "to forward", "sk": "preposlať", "example": "Could you forward me the email?"},
            {"en": "Let me know", "sk": "Daj mi vedieť", "example": "Let me know if that works for you."},
            {"en": "Best regards", "sk": "S pozdravom", "example": "Best regards, Anna"},
            {"en": "Looking forward to hearing from you", "sk": "Teším sa na vašu odpoveď", "example": "Looking forward to hearing from you."},
        ],
        "tips": [
            "Keď oslovuješ menom, ide čiarka a malé písmeno na ďalšom riadku: <em>Dear Ms Novak,</em> … V slovenčine zvyknutá veľká začiatočná litera po oslovení sa v angličtine nepoužíva.",
            "Formálne <strong>Yours sincerely</strong> použi, keď adresáta poznáš menom, <strong>Yours faithfully</strong> pri „Dear Sir or Madam“. Neutrálne <strong>Best regards</strong> sedí takmer vždy.",
            "Do telefónu sa nehovorí <em>Who are you?</em> — prirodzené je „Who's calling, please?“ alebo „Could I ask who's calling?“.",
        ],
        "related": ["praca-a-kancelaria", "pocitac-a-internet", "pracovny-pohovor"],
        "date": "2026-08-18",
    },
    {
        "slug": "farby-a-tvary",
        "title": "Anglické slovíčka: farby a tvary",
        "description": (
            "Anglické slovíčka o farbách a tvaroch — odtiene, vzory, základné "
            "geometrické tvary. 18 slov s vetami na opis vecí."
        ),
        "intro": (
            "Farby a tvary potrebuješ vždy, keď niečo opisuješ — v obchode, pri "
            "hľadaní stratenej batožiny aj v škole. Angličtina má navyše pár "
            "odtieňov, ktoré sa do slovenčiny prekladajú ťažko, a poradie "
            "prídavných mien pred podstatným menom má svoje pravidlo. Nižšie "
            "sú slová aj s vetami, na ktorých to uvidíš."
        ),
        "words": [
            {"en": "colour", "sk": "farba (UK)", "example": "What colour is your car?"},
            {"en": "light blue", "sk": "svetlomodrá", "example": "She wore a light blue shirt."},
            {"en": "dark green", "sk": "tmavozelená", "example": "The walls are dark green."},
            {"en": "grey", "sk": "sivá (UK)", "example": "The sky was grey all day."},
            {"en": "purple", "sk": "fialová", "example": "Purple is her favourite colour."},
            {"en": "brown", "sk": "hnedá", "example": "He has brown eyes."},
            {"en": "beige", "sk": "béžová", "example": "The sofa is beige."},
            {"en": "striped", "sk": "pruhovaný", "example": "I'd like the striped one."},
            {"en": "spotted", "sk": "bodkovaný", "example": "She bought a spotted scarf."},
            {"en": "plain", "sk": "jednofarebný", "example": "A plain white shirt is safest."},
            {"en": "bright", "sk": "výrazný (jasný)", "example": "That's a very bright yellow."},
            {"en": "square", "sk": "štvorec", "example": "The table is square."},
            {"en": "circle", "sk": "kruh", "example": "Draw a circle here."},
            {"en": "triangle", "sk": "trojuholník", "example": "The sign is a red triangle."},
            {"en": "rectangle", "sk": "obdĺžnik", "example": "The screen is a wide rectangle."},
            {"en": "round", "sk": "okrúhly", "example": "We sat at a round table."},
            {"en": "flat", "sk": "plochý", "example": "Put it on a flat surface."},
            {"en": "shape", "sk": "tvar", "example": "What shape is it?"},
        ],
        "tips": [
            "Britské <strong>colour</strong>, <strong>grey</strong> a <strong>favourite</strong> sú americké <strong>color</strong>, <strong>gray</strong>, <strong>favorite</strong>. Drž sa jednej varianty.",
            "Poradie prídavných mien: názor → veľkosť → vek → tvar → farba → pôvod → materiál. Preto <em>a nice big old round brown wooden table</em>.",
            "Pri opise vecí sa hodí väzba <strong>What colour / shape is it?</strong> — nie <em>Which colour has it?</em>.",
        ],
        "related": ["oblecenie-a-moda", "nakupovanie", "skola"],
        "date": "2026-08-18",
    },
]

# Rýchly index pre routu (slug → téma).
TOPICS_BY_SLUG = {t["slug"]: t for t in TOPICS}


def get_topic(slug: str) -> dict | None:
    return TOPICS_BY_SLUG.get(slug)


def related_topics(topic: dict) -> list[dict]:
    """Príbuzné témy ako plné záznamy (neexistujúce slugy ticho vynechá)."""
    return [TOPICS_BY_SLUG[s] for s in topic.get("related", []) if s in TOPICS_BY_SLUG]
