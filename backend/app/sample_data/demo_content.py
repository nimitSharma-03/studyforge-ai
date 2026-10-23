"""Synthetic demonstration lecture notes on foundational NLP concepts.

Written specifically for the StudyForge AI demo; not copied from any textbook.
"""

TITLE = "Foundations of Natural Language Processing (Demonstration Notes)"
NOTICE = (
    "Demonstration material only. These synthetic notes were written for this sample and summarise widely "
    "taught introductory ideas; they are not taken from any textbook."
)

SECTIONS: list[tuple[str, list[str]]] = [
    (
        "Introduction to Natural Language Processing",
        [
            "Natural language processing (NLP) is a branch of artificial intelligence that enables computers to "
            "analyse, understand and generate human language. NLP combines ideas from linguistics, computer science "
            "and statistics. Typical NLP applications include machine translation, sentiment analysis, chatbots, "
            "spam filtering and information retrieval.",
            "Human language is difficult for computers because it is ambiguous, context dependent and constantly "
            "changing. A single sentence can have several valid interpretations, so NLP systems must use context to "
            "choose the most likely meaning.",
            "Early NLP systems relied on hand-written rules, whereas modern systems learn patterns from large "
            "collections of text called corpora. A corpus is a large, structured collection of texts used to study "
            "language or train models.",
        ],
    ),
    (
        "Text Preprocessing",
        [
            "Text preprocessing is the process of cleaning and standardising raw text before analysis. Preprocessing "
            "usually includes lowercasing, removing punctuation, handling numbers and removing extra whitespace. The "
            "quality of preprocessing has a direct effect on every later stage of an NLP pipeline.",
            "Noise removal refers to deleting irrelevant content such as HTML tags, page numbers and repeated headers. "
            "Normalisation means converting text into a consistent form, for example expanding contractions or "
            "mapping different spellings of a word to one standard spelling.",
        ],
    ),
    (
        "Tokenization",
        [
            "Tokenization is the process of splitting text into smaller units called tokens. Tokens are usually words, "
            "subwords or punctuation marks. Sentence segmentation divides a paragraph into individual sentences, while "
            "word tokenization divides a sentence into words.",
            "Tokenization is not trivial because abbreviations such as Dr. and e.g. contain full stops that do not end "
            "a sentence. Subword tokenization methods such as Byte Pair Encoding split rare words into frequent "
            "smaller pieces, which helps models handle words they have never seen before.",
        ],
    ),
    (
        "Stop Words, Stemming and Lemmatization",
        [
            "Stop words are very common words such as the, is and and that carry little meaning on their own. Removing "
            "stop words reduces the size of the vocabulary and lets an algorithm focus on informative terms.",
            "Stemming is a technique that removes word suffixes using simple rules to obtain a root form. The Porter "
            "stemmer is a well-known rule-based stemming algorithm for English. Lemmatization is the process of "
            "reducing a word to its dictionary form, called the lemma, using vocabulary and morphological analysis.",
            "Stemming is fast but can produce non-words such as studi, whereas lemmatization is slower but returns "
            "valid dictionary words such as study.",
        ],
    ),
    (
        "Part-of-Speech Tagging and Named Entity Recognition",
        [
            "Part-of-speech tagging is the task of assigning a grammatical category, such as noun, verb or adjective, "
            "to each token in a sentence. Part-of-speech tags help later stages such as parsing and information "
            "extraction.",
            "Named entity recognition (NER) is the task of locating and classifying named entities such as people, "
            "organisations, locations and dates in text. Named entity recognition is used in search engines, news "
            "analysis and customer support systems to extract structured information from unstructured text.",
            "Hidden Markov Models and Conditional Random Fields are traditional sequence labelling models used for "
            "part-of-speech tagging and named entity recognition.",
        ],
    ),
    (
        "Text Representation: Bag of Words and TF-IDF",
        [
            "Machine learning algorithms require numerical input, so text must be converted into vectors. The "
            "bag-of-words model represents a document as a vector of word counts and ignores word order.",
            "Term frequency measures how often a term appears in a document. Inverse document frequency measures how "
            "rare a term is across the whole collection of documents. TF-IDF is a weighting scheme that multiplies "
            "term frequency by inverse document frequency.",
            "TF-IDF gives high weight to terms that are frequent in one document but rare in the collection, so common "
            "words receive low weight. Cosine similarity is a measure of similarity between two vectors based on the "
            "angle between them. Cosine similarity is used in information retrieval to rank documents by their "
            "relevance to a query.",
        ],
    ),
    (
        "Word Embeddings",
        [
            "Word embeddings are dense vector representations of words in which words with similar meanings have "
            "similar vectors. Unlike bag-of-words vectors, word embeddings capture semantic relationships between "
            "words.",
            "Word2Vec is a neural method that learns word embeddings by predicting words from their surrounding "
            "context. The distributional hypothesis states that words appearing in similar contexts tend to have "
            "similar meanings.",
            "Contextual embeddings produced by transformer models assign different vectors to the same word in "
            "different sentences, because the surrounding words change the representation.",
        ],
    ),
    (
        "Language Models",
        [
            "A language model is a model that assigns probabilities to sequences of words. An n-gram model estimates "
            "the probability of a word using only the previous n minus one words.",
            "Smoothing is a technique that assigns a small probability to word sequences that never appeared in the "
            "training corpus. Perplexity is a metric that measures how well a language model predicts a sample of "
            "text, and lower perplexity indicates a better model.",
            "Neural language models based on the transformer architecture use self-attention to relate every word in a "
            "sentence to every other word. Language models are used for text generation, autocomplete, speech "
            "recognition and machine translation.",
        ],
    ),
    (
        "Evaluation of NLP Systems",
        [
            "Precision is the proportion of predicted positive items that are actually correct. Recall is the "
            "proportion of actual positive items that the system successfully finds. The F1 score is the harmonic mean "
            "of precision and recall.",
            "Accuracy can be misleading on imbalanced datasets because a model can score highly by always predicting "
            "the majority class. A confusion matrix is a table that summarises correct and incorrect predictions for "
            "each class.",
            "BLEU is a metric used to evaluate machine translation by comparing system output with reference "
            "translations.",
        ],
    ),
]
