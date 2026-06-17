LESSON_STAGE_OBJECTIVES = {
    "context_question": "Diagnose what the student already understands about the topic.",
    "short_explanation": "Teach one clear concept with one bilingual example.",
    "more_examples": "Give three realistic examples and model pronunciation.",
    "comprehension": "Check if the student understands meaning before production.",
    "structure": "Show the sentence pattern or grammar formula clearly.",
    "exercise_1": "Practice one controlled answer with high chance of success.",
    "exercise_2": "Practice a second controlled answer with a small variation.",
    "production": "Make the student create a full sentence.",
    "conversation": "Use the structure in a real conversation question.",
    "expansion": "Connect the topic to the student's life or interests.",
    "challenge": "Close the lesson with a tiny mission and summarize progress.",
}


LEVEL_EXERCISE_STYLE = {
    "Basic": {
        "english_ratio": "30-40%",
        "exercise_type": "translation, fill-in-the-blank, one short sentence",
        "feedback": "Portuguese explanation with simple English examples",
        "advance_when": "student can understand one example and produce one short guided sentence",
    },
    "Basic 2": {
        "english_ratio": "40-50%",
        "exercise_type": "short answers, simple routine sentences, guided mini-dialogues",
        "feedback": "Portuguese explanation with more English prompts",
        "advance_when": "student can produce two simple sentences with minor support",
    },
    "Intermediate": {
        "english_ratio": "55-70%",
        "exercise_type": "sentence transformation, short answers, personal examples",
        "feedback": "mixed Portuguese and English, focusing on grammar and naturalness",
        "advance_when": "student can answer a personal question using the target structure",
    },
    "Advanced": {
        "english_ratio": "85-100%",
        "exercise_type": "opinion, storytelling, nuance, correction of naturalness",
        "feedback": "English feedback with concise correction notes",
        "advance_when": "student can explain ideas clearly with few blocking mistakes",
    },
    "Fluent": {
        "english_ratio": "100%",
        "exercise_type": "debate, nuance, idiomatic language, precision",
        "feedback": "English feedback focused on sophistication and style",
        "advance_when": "student can sustain a natural discussion and refine expression",
    },
}


PLACEMENT_RUBRIC = {
    "Basic": {
        "evidence": [
            "student knows isolated words or no English",
            "student cannot form independent sentences yet",
            "student needs Portuguese support most of the time",
        ],
        "start_lesson": 1,
    },
    "Basic 2": {
        "evidence": [
            "student can write simple memorized sentences",
            "student uses basic vocabulary about self, routine, likes, food, places",
            "student makes frequent grammar errors but meaning is often clear",
        ],
        "start_lesson": 11,
    },
    "Intermediate": {
        "evidence": [
            "student can answer personal questions in short paragraphs",
            "student can use present, past, or future with some mistakes",
            "student can describe experiences or plans",
        ],
        "start_lesson": 21,
    },
    "Advanced": {
        "evidence": [
            "student can explain opinions and abstract ideas",
            "student uses connectors and varied vocabulary",
            "student needs correction mostly for precision and naturalness",
        ],
        "start_lesson": 51,
    },
    "Fluent": {
        "evidence": [
            "student communicates naturally across complex topics",
            "student handles nuance, debate, storytelling, and negotiation",
            "student needs refinement, not basic instruction",
        ],
        "start_lesson": 61,
    },
}


CORRECTION_RUBRIC = {
    "meaning": "Did the student communicate the intended idea?",
    "grammar": "Did the student use the target structure correctly?",
    "vocabulary": "Did the student choose useful and natural words?",
    "pronunciation": "If audio was sent, was the phrase understandable and confident?",
    "independence": "Did the student answer without needing too much prompting?",
}


PRONUNCIATION_RUBRIC = {
    "understandability": "Could the spoken phrase be transcribed and understood?",
    "target_phrase": "Did the student attempt the requested phrase or answer?",
    "rhythm": "Does the phrase seem complete and natural from the transcription?",
    "confidence": "Is the answer clear enough to repeat and improve?",
    "safety_rule": "Do not claim phonetic certainty unless the system has explicit speech-analysis data.",
}


SPACED_REVIEW_INTERVALS = [1, 3, 7, 14, 30]


TOPIC_OBJECTIVES = {
    "Greetings": {
        "objective": "Greet someone and introduce yourself.",
        "can_do": "I can say hello, ask a name, and say my name.",
        "target_language": ["Hi.", "Hello.", "Good morning.", "What's your name?", "My name is..."],
        "controlled_exercises": [
            "Complete: My name ___ Ronan.",
            "Complete: ___ your name?",
            "Translate: Oi, meu nome e Ronan.",
        ],
        "speaking_task": "Send a short audio saying: Hi, my name is [your name].",
    },
    "Present Continuous": {
        "objective": "Talk about actions happening now.",
        "can_do": "I can say what I or another person is doing right now.",
        "target_language": ["I am studying.", "She is reading.", "They are playing soccer."],
        "controlled_exercises": [
            "Complete: I ___ studying.",
            "Complete: She ___ reading.",
            "Translate: Eu estou estudando ingles.",
        ],
        "speaking_task": "Send a short audio answering: What are you doing right now?",
    },
    "Restaurant Conversation": {
        "objective": "Order food or drink politely.",
        "can_do": "I can ask for food or water politely in English.",
        "target_language": ["Can I have water, please?", "I would like a coffee.", "The bill, please."],
        "controlled_exercises": [
            "Complete: Can I have ___, please?",
            "Translate: Eu gostaria de agua.",
            "Answer: What would you like?",
        ],
        "speaking_task": "Send a short audio ordering one item politely.",
    },
}


LESSON_OBJECTIVES_BY_NUMBER = {
    1: {
        "objective": "Greet someone and introduce yourself.",
        "can_do": "I can say hello, ask a name, and say my name.",
        "target_language": ["Hi.", "Hello.", "Good morning.", "What's your name?", "My name is..."],
        "controlled_exercises": ["Complete: My name ___ Ronan.", "Complete: ___ your name?", "Translate: Oi, meu nome e Ronan."],
        "speaking_task": "Send a short audio saying: Hi, my name is [your name].",
    },
    2: {
        "objective": "Say where you are from and recognize nationalities.",
        "can_do": "I can answer: Where are you from?",
        "target_language": ["Where are you from?", "I am from Brazil.", "I am Brazilian."],
        "controlled_exercises": ["Complete: I am ___ Brazil.", "Answer: Where are you from?", "Choose: Brazil / Brazilian."],
        "speaking_task": "Send a short audio saying where you are from.",
    },
    3: {
        "objective": "Use numbers from 0 to 100 and say your age.",
        "can_do": "I can say my age in English.",
        "target_language": ["How old are you?", "I am 25 years old.", "Numbers 0 to 100."],
        "controlled_exercises": ["Write the number: 25.", "Complete: I am ___ years old.", "Answer: How old are you?"],
        "speaking_task": "Send a short audio saying your age.",
    },
    4: {
        "objective": "Use the verb to be in simple sentences.",
        "can_do": "I can use am, is, and are.",
        "target_language": ["I am.", "You are.", "He is.", "She is.", "They are."],
        "controlled_exercises": ["Complete: I ___ Brazilian.", "Complete: She ___ a teacher.", "Translate: Ele e meu amigo."],
        "speaking_task": "Send a short audio with two sentences using am/is/are.",
    },
    5: {
        "objective": "Name family members and talk about family.",
        "can_do": "I can say who is in my family.",
        "target_language": ["father", "mother", "brother", "sister", "This is my..."],
        "controlled_exercises": ["Complete: This is my ___.", "Translate: Minha mae.", "Write one family sentence."],
        "speaking_task": "Send a short audio naming two family members.",
    },
    6: {
        "objective": "Talk about professions and work.",
        "can_do": "I can answer: What do you do?",
        "target_language": ["What do you do?", "I am a teacher.", "I work as a..."],
        "controlled_exercises": ["Complete: I am ___ teacher.", "Answer: What do you do?", "Translate: Eu sou estudante."],
        "speaking_task": "Send a short audio saying what you do.",
    },
    7: {
        "objective": "Use days and months in simple plans.",
        "can_do": "I can say days and months in English.",
        "target_language": ["Monday", "Tuesday", "January", "February", "My class is on..."],
        "controlled_exercises": ["Complete: My class is on ___.", "Write today's day.", "Translate: Minha aula e segunda."],
        "speaking_task": "Send a short audio saying one day and one month.",
    },
    8: {
        "objective": "Ask and tell the time.",
        "can_do": "I can answer: What time is it?",
        "target_language": ["What time is it?", "It is 9 o'clock.", "It is 9:30."],
        "controlled_exercises": ["Complete: It is ___ o'clock.", "Answer: What time is it?", "Translate: Sao sete horas."],
        "speaking_task": "Send a short audio telling the time now.",
    },
    9: {
        "objective": "Use colors to describe objects.",
        "can_do": "I can name colors and describe things.",
        "target_language": ["red", "blue", "green", "black", "white"],
        "controlled_exercises": ["Complete: My shirt is ___.", "Name three colors.", "Translate: O carro e vermelho."],
        "speaking_task": "Send a short audio naming three colors around you.",
    },
    10: {
        "objective": "Review basic personal information.",
        "can_do": "I can introduce myself with basic details.",
        "target_language": ["My name is...", "I am from...", "I am ... years old.", "I am a..."],
        "controlled_exercises": ["Write 3 sentences about yourself.", "Answer: What's your name?", "Answer: Where are you from?"],
        "speaking_task": "Send a short audio introducing yourself.",
    },
    11: {
        "objective": "Describe a simple daily routine.",
        "can_do": "I can say what I do every day.",
        "target_language": ["I wake up.", "I work.", "I study.", "I go home."],
        "controlled_exercises": ["Complete: I ___ up at 7.", "Write one routine sentence.", "Translate: Eu estudo ingles."],
        "speaking_task": "Send a short audio with two routine actions.",
    },
    12: {
        "objective": "Use Simple Present for habits.",
        "can_do": "I can talk about habits and routines.",
        "target_language": ["I study English.", "She works.", "He likes coffee."],
        "controlled_exercises": ["Complete: I ___ English.", "Complete: She ___ every day.", "Translate: Eu trabalho de manha."],
        "speaking_task": "Send a short audio saying one habit.",
    },
    13: {
        "objective": "Express likes and dislikes.",
        "can_do": "I can say what I like and do not like.",
        "target_language": ["I like music.", "I don't like coffee.", "Do you like...?"],
        "controlled_exercises": ["Complete: I ___ pizza.", "Complete: I don't ___ coffee.", "Answer: What do you like?"],
        "speaking_task": "Send a short audio saying one thing you like.",
    },
    14: {
        "objective": "Use common food vocabulary.",
        "can_do": "I can name foods and say what I eat.",
        "target_language": ["rice", "beans", "bread", "water", "coffee"],
        "controlled_exercises": ["Name three foods.", "Complete: I eat ___.", "Translate: Eu bebo agua."],
        "speaking_task": "Send a short audio naming three foods.",
    },
    15: {
        "objective": "Order food politely at a restaurant.",
        "can_do": "I can ask for food or water politely.",
        "target_language": ["Can I have water, please?", "I would like a coffee.", "The bill, please."],
        "controlled_exercises": ["Complete: Can I have ___, please?", "Translate: Eu gostaria de agua.", "Answer: What would you like?"],
        "speaking_task": "Send a short audio ordering one item politely.",
    },
    16: {
        "objective": "Buy items and ask about prices.",
        "can_do": "I can ask price and size when shopping.",
        "target_language": ["How much is it?", "I need a small size.", "I would like this."],
        "controlled_exercises": ["Complete: How much ___ it?", "Translate: Eu quero este.", "Ask the price of a shirt."],
        "speaking_task": "Send a short audio asking the price of something.",
    },
    17: {
        "objective": "Describe the weather.",
        "can_do": "I can say what the weather is like.",
        "target_language": ["It is sunny.", "It is raining.", "It is cold.", "It is hot."],
        "controlled_exercises": ["Complete: It ___ sunny.", "Answer: How is the weather today?", "Translate: Esta frio."],
        "speaking_task": "Send a short audio describing today's weather.",
    },
    18: {
        "objective": "Name rooms and objects at home.",
        "can_do": "I can describe my house with simple words.",
        "target_language": ["kitchen", "bedroom", "bathroom", "chair", "table"],
        "controlled_exercises": ["Name three rooms.", "Complete: The table is in the ___.", "Translate: Meu quarto."],
        "speaking_task": "Send a short audio naming two things in your house.",
    },
    19: {
        "objective": "Name places in the city.",
        "can_do": "I can talk about places around town.",
        "target_language": ["bank", "school", "market", "hospital", "restaurant"],
        "controlled_exercises": ["Name three places.", "Complete: I go to the ___.", "Translate: Eu vou ao mercado."],
        "speaking_task": "Send a short audio naming two places in your city.",
    },
    20: {
        "objective": "Review Basic 2 speaking skills.",
        "can_do": "I can talk about routine, likes, food, weather, home, and city.",
        "target_language": ["I like...", "I work...", "It is sunny.", "I go to..."],
        "controlled_exercises": ["Write 4 simple sentences.", "Answer one routine question.", "Answer one food question."],
        "speaking_task": "Send a short audio with three sentences about your day.",
    },
    21: {
        "objective": "Talk about actions happening now.",
        "can_do": "I can say what I or another person is doing right now.",
        "target_language": ["I am studying.", "She is reading.", "They are playing soccer."],
        "controlled_exercises": ["Complete: I ___ studying.", "Complete: She ___ reading.", "Translate: Eu estou estudando ingles."],
        "speaking_task": "Send a short audio answering: What are you doing right now?",
    },
    22: {
        "objective": "Talk about finished past actions.",
        "can_do": "I can say what I did yesterday.",
        "target_language": ["I worked yesterday.", "I studied English.", "Did you travel?"],
        "controlled_exercises": ["Complete: I ___ yesterday.", "Translate: Eu trabalhei ontem.", "Answer: What did you do yesterday?"],
        "speaking_task": "Send a short audio saying two things you did yesterday.",
    },
    23: {
        "objective": "Use regular verbs in the past.",
        "can_do": "I can add -ed to regular verbs in past sentences.",
        "target_language": ["worked", "studied", "played", "watched"],
        "controlled_exercises": ["Change: work -> ___.", "Complete: I ___ soccer.", "Translate: Eu estudei ontem."],
        "speaking_task": "Send a short audio with one regular past sentence.",
    },
    24: {
        "objective": "Use common irregular past verbs.",
        "can_do": "I can use some common irregular verbs in the past.",
        "target_language": ["went", "had", "saw", "bought", "did"],
        "controlled_exercises": ["Change: go -> ___.", "Complete: I ___ to work.", "Translate: Eu fui ao mercado."],
        "speaking_task": "Send a short audio with one irregular past sentence.",
    },
    25: {
        "objective": "Talk about personal experiences.",
        "can_do": "I can describe an experience in simple English.",
        "target_language": ["I visited...", "I tried...", "It was interesting."],
        "controlled_exercises": ["Complete: I visited ___.", "Write one experience sentence.", "Answer: Was it good?"],
        "speaking_task": "Send a short audio about one experience.",
    },
    26: {
        "objective": "Use useful travel English.",
        "can_do": "I can ask simple questions when traveling.",
        "target_language": ["Where is the station?", "I need help.", "How much is a ticket?"],
        "controlled_exercises": ["Complete: Where is the ___?", "Translate: Eu preciso de ajuda.", "Ask for a ticket."],
        "speaking_task": "Send a short audio asking one travel question.",
    },
    27: {
        "objective": "Handle simple airport situations.",
        "can_do": "I can use basic airport phrases.",
        "target_language": ["check-in", "boarding pass", "luggage", "gate"],
        "controlled_exercises": ["Complete: I need my boarding ___.", "Translate: Onde e o portao?", "Ask about luggage."],
        "speaking_task": "Send a short audio asking where the gate is.",
    },
    28: {
        "objective": "Make basic hotel requests.",
        "can_do": "I can check in and ask for help at a hotel.",
        "target_language": ["I have a reservation.", "Can I check in?", "I need a towel."],
        "controlled_exercises": ["Complete: I have a ___.", "Translate: Eu preciso de uma toalha.", "Ask to check in."],
        "speaking_task": "Send a short audio checking in at a hotel.",
    },
    29: {
        "objective": "Ask for and give simple directions.",
        "can_do": "I can ask where a place is.",
        "target_language": ["Go straight.", "Turn left.", "Turn right.", "Where is...?"],
        "controlled_exercises": ["Complete: Turn ___.", "Translate: Va reto.", "Ask where the bank is."],
        "speaking_task": "Send a short audio asking for directions.",
    },
    30: {
        "objective": "Review A2 travel and past communication.",
        "can_do": "I can talk about past actions and travel situations.",
        "target_language": ["I went...", "I need...", "Where is...?", "Can I...?"],
        "controlled_exercises": ["Write one past sentence.", "Ask one travel question.", "Describe one place."],
        "speaking_task": "Send a short audio about a past trip or place.",
    },
    31: {
        "objective": "Use will for future decisions and predictions.",
        "can_do": "I can make simple future sentences with will.",
        "target_language": ["I will study.", "It will rain.", "I will call you."],
        "controlled_exercises": ["Complete: I ___ study tomorrow.", "Translate: Eu vou ligar para voce.", "Make one prediction."],
        "speaking_task": "Send a short audio with one future sentence using will.",
    },
    32: {
        "objective": "Use going to for plans.",
        "can_do": "I can talk about plans with going to.",
        "target_language": ["I am going to travel.", "She is going to study.", "We are going to work."],
        "controlled_exercises": ["Complete: I am going ___ study.", "Translate: Eu vou viajar.", "Write one plan."],
        "speaking_task": "Send a short audio saying one plan.",
    },
    33: {
        "objective": "Compare two things.",
        "can_do": "I can use comparatives like bigger and better.",
        "target_language": ["bigger than", "better than", "more expensive than"],
        "controlled_exercises": ["Complete: English is ___ than before.", "Compare two cities.", "Translate: Este e mais barato."],
        "speaking_task": "Send a short audio comparing two things you like.",
    },
    34: {
        "objective": "Use superlatives to describe extremes.",
        "can_do": "I can say the best, biggest, or most important.",
        "target_language": ["the best", "the biggest", "the most important"],
        "controlled_exercises": ["Complete: This is the ___ movie.", "Translate: O melhor dia.", "Name the best food."],
        "speaking_task": "Send a short audio saying the best thing in your city.",
    },
    35: {
        "objective": "Use modal verbs for ability, advice, and obligation.",
        "can_do": "I can use can, should, and must in simple contexts.",
        "target_language": ["I can...", "You should...", "You must..."],
        "controlled_exercises": ["Complete: I ___ speak English.", "Complete: You ___ study.", "Translate: Voce deve praticar."],
        "speaking_task": "Send a short audio giving one piece of advice.",
    },
    36: {
        "objective": "Use can and could for ability and polite requests.",
        "can_do": "I can ask politely with could.",
        "target_language": ["Can you help me?", "Could you repeat that?", "I can speak a little."],
        "controlled_exercises": ["Complete: Could you ___ that?", "Translate: Voce pode me ajudar?", "Ask a polite request."],
        "speaking_task": "Send a short audio asking politely for help.",
    },
    37: {
        "objective": "Use should and must for advice and obligation.",
        "can_do": "I can give advice and express obligation.",
        "target_language": ["You should practice.", "You must arrive early.", "I should sleep."],
        "controlled_exercises": ["Complete: You ___ study more.", "Translate: Voce deve chegar cedo.", "Give one advice sentence."],
        "speaking_task": "Send a short audio giving advice to a friend.",
    },
    38: {
        "objective": "Answer basic job interview questions.",
        "can_do": "I can introduce myself in a job interview.",
        "target_language": ["Tell me about yourself.", "I have experience in...", "My strength is..."],
        "controlled_exercises": ["Complete: My strength is ___.", "Answer: Tell me about yourself.", "Translate: Eu tenho experiencia."],
        "speaking_task": "Send a short audio introducing yourself for a job.",
    },
    39: {
        "objective": "Use professional phone call language.",
        "can_do": "I can start and manage a simple phone call.",
        "target_language": ["Can I speak to...?", "Please hold.", "I will call you back."],
        "controlled_exercises": ["Complete: Can I speak ___ Ronan?", "Translate: Eu vou retornar a ligacao.", "Start a phone call."],
        "speaking_task": "Send a short audio starting a professional call.",
    },
    40: {
        "objective": "Review B1 future, comparisons, modals, and work situations.",
        "can_do": "I can speak about plans, advice, comparisons, and work.",
        "target_language": ["I will...", "I am going to...", "You should...", "better than"],
        "controlled_exercises": ["Write one plan.", "Give one advice.", "Compare two jobs or cities."],
        "speaking_task": "Send a short audio summarizing your goals in English.",
    },
    41: {
        "objective": "Use Present Perfect for experiences and recent actions.",
        "can_do": "I can say what I have done.",
        "target_language": ["I have visited...", "She has finished.", "Have you ever...?"],
        "controlled_exercises": ["Complete: I have ___ English.", "Translate: Eu ja visitei Sao Paulo.", "Ask: Have you ever...?"],
        "speaking_task": "Send a short audio about one experience you have had.",
    },
    42: {
        "objective": "Choose between Present Perfect and Past Simple.",
        "can_do": "I can separate experience from finished past time.",
        "target_language": ["I have been there.", "I went there yesterday.", "Have you ever...?"],
        "controlled_exercises": ["Choose: have been / went.", "Translate: Eu fui ontem.", "Write one experience and one finished past action."],
        "speaking_task": "Send a short audio with one experience and one past detail.",
    },
    43: {
        "objective": "Use Passive Voice to focus on actions and results.",
        "can_do": "I can say when something is done by someone or something.",
        "target_language": ["It is made in Brazil.", "The email was sent.", "The project was finished."],
        "controlled_exercises": ["Complete: The email ___ sent.", "Translate: O projeto foi terminado.", "Change active to passive."],
        "speaking_task": "Send a short audio describing something that was made or done.",
    },
    44: {
        "objective": "Use First Conditional for real future possibilities.",
        "can_do": "I can say what will happen if something happens.",
        "target_language": ["If I study, I will improve.", "If it rains, I will stay home."],
        "controlled_exercises": ["Complete: If I study, I ___ improve.", "Translate: Se chover, eu vou ficar em casa.", "Make one if sentence."],
        "speaking_task": "Send a short audio with one real future condition.",
    },
    45: {
        "objective": "Use Second Conditional for hypothetical situations.",
        "can_do": "I can talk about imaginary situations.",
        "target_language": ["If I had more time, I would study.", "If I were rich..."],
        "controlled_exercises": ["Complete: If I had time, I ___ travel.", "Translate: Se eu fosse rico.", "Make one imaginary sentence."],
        "speaking_task": "Send a short audio answering: What would you do with more time?",
    },
    46: {
        "objective": "Use common phrasal verbs.",
        "can_do": "I can understand and use useful phrasal verbs.",
        "target_language": ["wake up", "look for", "turn on", "give up"],
        "controlled_exercises": ["Complete: I wake ___ at 7.", "Translate: Eu estou procurando meu celular.", "Use one phrasal verb."],
        "speaking_task": "Send a short audio with one phrasal verb in context.",
    },
    47: {
        "objective": "Use practical Business English vocabulary.",
        "can_do": "I can talk about work tasks professionally.",
        "target_language": ["deadline", "meeting", "client", "project", "follow up"],
        "controlled_exercises": ["Complete: I have a ___ today.", "Translate: Eu preciso fazer follow up.", "Write one work sentence."],
        "speaking_task": "Send a short audio describing one work task.",
    },
    48: {
        "objective": "Participate in meetings.",
        "can_do": "I can share an opinion in a meeting.",
        "target_language": ["I agree.", "I have a question.", "In my opinion...", "Could you clarify?"],
        "controlled_exercises": ["Complete: In my ___...", "Translate: Eu tenho uma pergunta.", "Ask for clarification."],
        "speaking_task": "Send a short audio giving an opinion in a meeting.",
    },
    49: {
        "objective": "Present ideas clearly.",
        "can_do": "I can start a short presentation.",
        "target_language": ["Today I will talk about...", "First...", "The main point is..."],
        "controlled_exercises": ["Complete: Today I will talk ___.", "Translate: O ponto principal e...", "Write an opening sentence."],
        "speaking_task": "Send a short audio opening a presentation.",
    },
    50: {
        "objective": "Review B2 grammar and professional communication.",
        "can_do": "I can use B2 structures in work and study contexts.",
        "target_language": ["I have...", "It was...", "If I...", "In my opinion..."],
        "controlled_exercises": ["Write one work sentence.", "Write one conditional sentence.", "Write one opinion sentence."],
        "speaking_task": "Send a short audio summarizing a professional goal.",
    },
    51: {
        "objective": "Use more precise advanced vocabulary.",
        "can_do": "I can choose stronger and more precise words.",
        "target_language": ["significant", "efficient", "reliable", "challenging", "valuable"],
        "controlled_exercises": ["Replace 'good' with a stronger word.", "Write one sentence with significant.", "Explain one advanced word."],
        "speaking_task": "Send a short audio using one advanced word naturally.",
    },
    52: {
        "objective": "Understand and use common idioms.",
        "can_do": "I can use simple idioms in natural contexts.",
        "target_language": ["break the ice", "on the same page", "a piece of cake"],
        "controlled_exercises": ["Choose the meaning of 'break the ice'.", "Use 'on the same page'.", "Rewrite one literal sentence with an idiom."],
        "speaking_task": "Send a short audio using one idiom.",
    },
    53: {
        "objective": "Understand natural informal English and slang carefully.",
        "can_do": "I can recognize informal expressions without overusing them.",
        "target_language": ["What's up?", "No worries.", "That sounds cool.", "I'm into..."],
        "controlled_exercises": ["Translate: No worries.", "Use: I'm into...", "Choose formal or informal context."],
        "speaking_task": "Send a short audio using one informal phrase naturally.",
    },
    54: {
        "objective": "Tell a short story with structure.",
        "can_do": "I can tell a short story with beginning, middle, and end.",
        "target_language": ["First", "Then", "After that", "Finally"],
        "controlled_exercises": ["Order story connectors.", "Write a 3-line story.", "Add one connector to a sentence."],
        "speaking_task": "Send a short audio telling a 20-second story.",
    },
    55: {
        "objective": "Express and defend an opinion in a debate.",
        "can_do": "I can give an opinion and one reason.",
        "target_language": ["I believe...", "My main reason is...", "I see your point, but..."],
        "controlled_exercises": ["Complete: I believe ___.", "Give one reason.", "Respond politely to disagreement."],
        "speaking_task": "Send a short audio defending one opinion.",
    },
    56: {
        "objective": "Use persuasive language.",
        "can_do": "I can make a simple persuasive argument.",
        "target_language": ["The benefit is...", "This matters because...", "I recommend..."],
        "controlled_exercises": ["Complete: I recommend ___.", "Give one benefit.", "Make one persuasive sentence."],
        "speaking_task": "Send a short audio recommending something.",
    },
    57: {
        "objective": "Improve understanding of natural speech.",
        "can_do": "I can notice reductions and key words in natural English.",
        "target_language": ["gonna", "wanna", "kinda", "sounds like"],
        "controlled_exercises": ["Match gonna = going to.", "Rewrite wanna formally.", "Identify the key word in a sentence."],
        "speaking_task": "Send a short audio repeating one natural phrase clearly.",
    },
    58: {
        "objective": "Use formal and academic English.",
        "can_do": "I can express an idea in a more formal way.",
        "target_language": ["This suggests that...", "According to...", "The evidence shows..."],
        "controlled_exercises": ["Complete: This suggests ___.", "Rewrite an informal sentence formally.", "Use 'according to'."],
        "speaking_task": "Send a short audio explaining one idea formally.",
    },
    59: {
        "objective": "Speak clearly to an audience.",
        "can_do": "I can organize a short public speaking message.",
        "target_language": ["Today I want to share...", "My first point is...", "To conclude..."],
        "controlled_exercises": ["Write an opening.", "Write one main point.", "Write a closing sentence."],
        "speaking_task": "Send a short audio with a mini speech opening.",
    },
    60: {
        "objective": "Review advanced communication skills.",
        "can_do": "I can communicate opinions, stories, and formal ideas more clearly.",
        "target_language": ["I believe...", "First...", "This suggests...", "To conclude..."],
        "controlled_exercises": ["Write one opinion.", "Write one formal sentence.", "Write one story connector sentence."],
        "speaking_task": "Send a short audio summarizing your progress.",
    },
    61: {
        "objective": "Discuss political ideas respectfully.",
        "can_do": "I can express a political opinion without sounding aggressive.",
        "target_language": ["From my perspective...", "I understand the concern.", "A possible solution is..."],
        "controlled_exercises": ["State one neutral opinion.", "Use 'from my perspective'.", "Give one possible solution."],
        "speaking_task": "Send a short audio giving a respectful opinion.",
    },
    62: {
        "objective": "Discuss technology trends and impact.",
        "can_do": "I can talk about how technology affects life or work.",
        "target_language": ["Technology has changed...", "The main impact is...", "This could lead to..."],
        "controlled_exercises": ["Complete: Technology has changed ___.", "Give one impact.", "Predict one result."],
        "speaking_task": "Send a short audio about one technology trend.",
    },
    63: {
        "objective": "Discuss artificial intelligence in English.",
        "can_do": "I can explain one benefit and one risk of AI.",
        "target_language": ["AI can help with...", "One risk is...", "In the long term..."],
        "controlled_exercises": ["Give one AI benefit.", "Give one AI risk.", "Use 'in the long term'."],
        "speaking_task": "Send a short audio giving your opinion about AI.",
    },
    64: {
        "objective": "Discuss psychology and behavior.",
        "can_do": "I can describe emotions, habits, and behavior.",
        "target_language": ["People tend to...", "This behavior shows...", "It depends on..."],
        "controlled_exercises": ["Complete: People tend to ___.", "Describe one habit.", "Use 'it depends on'."],
        "speaking_task": "Send a short audio explaining one habit or behavior.",
    },
    65: {
        "objective": "Discuss abstract philosophical ideas.",
        "can_do": "I can explain an abstract idea with an example.",
        "target_language": ["The idea of...", "This raises a question.", "For instance..."],
        "controlled_exercises": ["Use 'for instance'.", "Ask one abstract question.", "Explain one idea simply."],
        "speaking_task": "Send a short audio explaining one abstract idea.",
    },
    66: {
        "objective": "Discuss business strategy and decisions.",
        "can_do": "I can explain a business decision and its reason.",
        "target_language": ["The strategy is...", "The market needs...", "The main challenge is..."],
        "controlled_exercises": ["Complete: The strategy is ___.", "Name one challenge.", "Explain one business decision."],
        "speaking_task": "Send a short audio explaining one business idea.",
    },
    67: {
        "objective": "Discuss leadership scenarios.",
        "can_do": "I can talk about leadership qualities and decisions.",
        "target_language": ["A good leader should...", "The team needs...", "I would handle it by..."],
        "controlled_exercises": ["Complete: A good leader should ___.", "Give one team need.", "Explain one leadership action."],
        "speaking_task": "Send a short audio describing a good leader.",
    },
    68: {
        "objective": "Negotiate and seek compromise.",
        "can_do": "I can propose a compromise politely.",
        "target_language": ["Would you be open to...?", "What if we...?", "Let's find a middle ground."],
        "controlled_exercises": ["Complete: Would you be open to ___?", "Propose one compromise.", "Use 'middle ground'."],
        "speaking_task": "Send a short audio proposing a compromise.",
    },
    69: {
        "objective": "Discuss cultural differences respectfully.",
        "can_do": "I can compare cultures without stereotyping.",
        "target_language": ["In my culture...", "One difference is...", "It is common to..."],
        "controlled_exercises": ["Complete: In my culture ___.", "Name one difference.", "Use 'it is common to'."],
        "speaking_task": "Send a short audio describing one cultural difference.",
    },
    70: {
        "objective": "Complete a final communication assessment.",
        "can_do": "I can show my progress through speaking, writing, and conversation.",
        "target_language": ["introduction", "opinion", "story", "problem-solving", "reflection"],
        "controlled_exercises": ["Introduce yourself.", "Give an opinion.", "Tell a short story."],
        "speaking_task": "Send a final short audio summarizing your English goal and progress.",
    },
}


def normalize_level(level: str):
    if level in LEVEL_EXERCISE_STYLE:
        return level

    if level and "advanced" in level.lower():
        return "Advanced"

    if level and "fluent" in level.lower():
        return "Fluent"

    if level and "intermediate" in level.lower():
        return "Intermediate"

    if level and "basic 2" in level.lower():
        return "Basic 2"

    return "Basic"


def build_default_lesson_design(lesson: dict):
    focus = lesson.get("focus", "")
    title = lesson.get("title", "English")

    return {
        "objective": f"Use {title} in a practical WhatsApp conversation.",
        "can_do": f"I can understand and use basic language about {title}.",
        "target_language": [item.strip() for item in focus.split(";") if item.strip()][:5],
        "controlled_exercises": [
            f"Write one short sentence using: {title}.",
            f"Translate one useful phrase connected to: {focus}.",
            f"Answer one simple question about: {title}.",
        ],
        "speaking_task": f"Send a short audio using one phrase from {title}.",
    }


def get_lesson_design(lesson: dict):
    lesson_number = lesson.get("number")

    if lesson_number in LESSON_OBJECTIVES_BY_NUMBER:
        return LESSON_OBJECTIVES_BY_NUMBER[lesson_number]

    return TOPIC_OBJECTIVES.get(
        lesson.get("title", ""),
        build_default_lesson_design(lesson)
    )


def get_level_pedagogy(level: str):
    return LEVEL_EXERCISE_STYLE[normalize_level(level)]


def build_pedagogical_context(lesson: dict, level: str, stage: str):
    design = get_lesson_design(lesson)
    level_style = get_level_pedagogy(level)
    stage_objective = LESSON_STAGE_OBJECTIVES.get(stage, "Continue the guided lesson.")

    return (
        "Pedagogical design:\n"
        f"- Lesson objective: {design['objective']}\n"
        f"- Can-do statement: {design['can_do']}\n"
        f"- Current stage objective: {stage_objective}\n"
        f"- Target language: {', '.join(design['target_language']) or lesson.get('focus', '')}\n"
        f"- Controlled exercises: {' | '.join(design['controlled_exercises'])}\n"
        f"- Speaking task: {design['speaking_task']}\n"
        f"- Level English ratio: {level_style['english_ratio']}\n"
        f"- Exercise style: {level_style['exercise_type']}\n"
        f"- Feedback style: {level_style['feedback']}\n"
        f"- Advancement criterion: {level_style['advance_when']}\n"
        f"- Correction rubric: meaning, grammar, vocabulary, pronunciation, independence\n"
        f"- Pronunciation rubric: understandability, target phrase, rhythm, confidence\n"
        f"- Spaced review intervals in days: {', '.join(str(day) for day in SPACED_REVIEW_INTERVALS)}"
    )


def get_advancement_criterion(level: str):
    return get_level_pedagogy(level)["advance_when"]


def get_placement_rubric_text():
    lines = ["Placement rubric:"]

    for level, data in PLACEMENT_RUBRIC.items():
        lines.append(f"- {level}: " + "; ".join(data["evidence"]))

    return "\n".join(lines)
