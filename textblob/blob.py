# -*- coding: utf-8 -*-
'''Wrappers for various units of text, including the main
:class:`TextBlob <textblob.blob.TextBlob>`, :class:`Word <textblob.blob.Word>`,
and :class:`WordList <textblob.blob.WordList>` classes.
Example usage: ::

    >>> from textblob import TextBlob
    >>> b = TextBlob("Simple is better than complex.")
    >>> b.tags
    [(u'Simple', u'NN'), (u'is', u'VBZ'), (u'better', u'JJR'), (u'than', u'IN'), (u'complex', u'NN')]
    >>> b.noun_phrases
    WordList([u'simple'])
    >>> b.words
    WordList([u'Simple', u'is', u'better', u'than', u'complex'])
    >>> b.sentiment
    (0.06666666666666667, 0.41904761904761906)
    >>> b.words[0].synsets()[0]
    Synset('simple.n.01')

.. versionchanged:: 0.8.0
    These classes are now imported from ``textblob`` rather than ``text.blob``.
'''
from __future__ import unicode_literals, absolute_import
import sys
import json
import string as pystring
from collections import defaultdict
import logging

from textblob.packages import nltk
from textblob.decorators import cached_property, requires_nltk_corpus
from textblob.utils import lowerstrip, PUNCTUATION_REGEX
from textblob.inflect import singularize as _singularize, pluralize as _pluralize
from textblob.mixins import BlobComparableMixin, StringlikeMixin
from textblob.compat import unicode, basestring
from textblob.base import (BaseNPExtractor, BaseTagger, BaseTokenizer,
                       BaseSentimentAnalyzer, BaseParser)
from textblob.np_extractors import FastNPExtractor
from textblob.taggers import PatternTagger
from textblob.tokenizers import WordTokenizer, SentenceTokenizer
from textblob.sentiments import PatternAnalyzer
from textblob.parsers import PatternParser
from textblob.translate import Translator
from textblob.en import suggest

# Wordnet interface
# NOTE: textblob.wordnet is not imported so that the wordnet corpus can be lazy-loaded
_wordnet = nltk.corpus.wordnet
logger = logging.getLogger(__name__)


class Word(unicode):

    '''A simple word representation. Includes methods for inflection,
    translation, and WordNet integration.
    '''

    translator = Translator()

    def __new__(cls, string, pos_tag=None):
        '''Return a new instance of the class. It is necessary to override
        this method in order to handle the extra pos_tag argument in the
        constructor.
        '''
        return super(Word, cls).__new__(cls, string)

    def __init__(self, string, pos_tag=None):
        self.string = string
        self.pos_tag = pos_tag

    def __repr__(self):
        return repr(self.string)

    def __str__(self):
        return self.string

    def singularize(self):
        '''Return the singular version of the word as a string.'''
        return Word(_singularize(self.string))

    def pluralize(self):
        '''Return the plural version of the word as a string.'''
        return Word(_pluralize(self.string))

    def translate(self, from_lang=None, to="en"):
        '''Translate the word to another language using Google's
        Translate API.

        .. versionadded:: 0.5.0
        '''
        if from_lang is None:
            from_lang = self.translator.detect(self.string)
        return self.translator.translate(self.string,
                                        from_lang=from_lang, to_lang=to)

    def detect_language(self):
        '''Detect the word's language using Google's Translate API.

        .. versionadded:: 0.5.0
        '''
        return self.translator.detect(self.string)

    def spellcheck(self):
        '''Return a list of (word, confidence) tuples of spelling corrections.

        Based on: Peter Norvig, "How to Write a Spelling Corrector"
        (http://norvig.com/spell-correct.html) as implemented in the pattern
        library.

        .. versionadded:: 0.6.0
        '''
        return suggest(self.string)

    def correct(self):
        '''Correct the spelling of the word. Returns the word with the highest
        confidence using the spelling corrector.

        .. versionadded:: 0.6.0
        '''
        return Word(self.spellcheck()[0][0])

    @cached_property
    @requires_nltk_corpus
    def lemma(self):
        '''Return the lemma of this word using Wordnet's morphy function.
        '''
        return self.lemmatize(pos=None)

    @requires_nltk_corpus
    def lemmatize(self, pos=None):
        '''Return the lemma for a word using WordNet's morphy function.

        :param pos: Part of speech to filter upon. If `None`, defaults to
            ``_wordnet.NOUN``.

        .. versionadded:: 0.8.1
        '''
        if pos is None:
            pos = _wordnet.NOUN
        lemmatizer = nltk.stem.WordNetLemmatizer()
        return lemmatizer.lemmatize(self.string, pos)

    @cached_property
    def synsets(self):
        '''The list of Synset objects for this Word.

        :rtype: list of Synsets

        .. versionadded:: 0.7.0
        '''
        return self.get_synsets(pos=None)

    @cached_property
    def definitions(self):
        '''The list of definitions for this word. Each definition corresponds
        to a synset.

        .. versionadded:: 0.7.0
        '''
        return self.define(pos=None)

    def get_synsets(self, pos=None):
        '''Return a list of Synset objects for this word.

        :param pos: A part-of-speech tag to filter upon. If ``None``, all
            synsets for all parts of speech will be loaded.

        :rtype: list of Synsets

        .. versionadded:: 0.7.0
        '''
        return _wordnet.synsets(self.string, pos)

    def define(self, pos=None):
        '''Return a list of definitions for this word. Each definition
        corresponds to a synset for this word.

        :param pos: A part-of-speech tag to filter upon. If ``None``, definitions
            for all parts of speech will be loaded.

        .. versionadded:: 0.7.0
        '''
        return [syn.definition for syn in self.get_synsets(pos=pos)]


class WordList(list):

    '''A list-like collection of words.'''

    def __init__(self, collection):
        '''Initialize a WordList. Takes a collection of strings as
        its only argument.
        '''
        self._collection = [Word(w) for w in collection]
        super(WordList, self).__init__(self._collection)

    def __str__(self):
        return str(self._collection)

    def __repr__(self):
        '''Returns a string representation for debugging.'''
        class_name = self.__class__.__name__
        # String representation of words
        strings = [unicode(w) for w in self._collection]
        if len(self) > 60:
            return '{cls}({beginning}...{end})'.format(cls=class_name,
                                                beginning=strings[:3],
                                                end=strings[-3:])
        else:
            return '{cls}({lst})'.format(cls=class_name, lst=strings)

    def __getitem__(self, key):
        '''Returns a string at the given index.'''
        if isinstance(key, slice):
            return self.__class__(self._collection[key])
        else:
            return self._collection[key]

    def __getslice__(self, i, j):
        # This is included for Python 2.* compatibility
        return self.__class__(self._collection[i:j])

    def __iter__(self):
        return iter(self._collection)

    def count(self, strg, case_sensitive=False, *args, **kwargs):
        """Get the count of a word or phrase `s` within this WordList.

        :param strg: The string to count.
        :param case_sensitive: A boolean, whether or not the search is case-sensitive.
        """
        if not case_sensitive:
            return [word.lower() for word in self].count(strg.lower(), *args,
                    **kwargs)
        return self._collection.count(strg, *args, **kwargs)

    def append(self, obj):
        '''Append an object to end. If the object is a string, appends a
        ``Word`` object.
        '''
        if isinstance(obj, basestring):
            return self._collection.append(Word(obj))
        else:
            return self._collection.append(obj)

    def extend(self, iterable):
        '''Extend WordList by appending alements from ``iterable``. If an element
        is a string, appends a ``Word`` object.
        '''
        [self._collection.append(Word(e) if isinstance(e, basestring) else e)
            for e in iterable]
        return self

    def upper(self):
        '''Return a new WordList with each word upper-cased.'''
        return self.__class__([word.upper() for word in self])

    def lower(self):
        '''Return a new WordList with each word lower-cased.'''
        return self.__class__([word.lower() for word in self])

    def singularize(self):
        '''Return the single version of each word in this WordList.'''
        return self.__class__([word.singularize() for word in self])

    def pluralize(self):
        '''Return the plural version of each word in this WordList.'''
        return self.__class__([word.pluralize() for word in self])

    def lemmatize(self):
        '''Return the lemma of each word in this WordList.'''
        return self.__class__([word.lemmatize() for word in self])


def _validated_param(obj, name, base_class, default, base_class_name=None):
    '''Validates a parameter passed to __init__. Makes sure that obj is
    the correct class. Return obj if it's not None or falls back to default

    :param obj: The object passed in.
    :param name: The name of the parameter.
    :param base_class: The class that obj must inherit from.
    :param default: The default object to fall back upon if obj is None.
    '''
    base_class_name = base_class_name if base_class_name else base_class.__name__
    if obj is not None and not isinstance(obj, base_class):
        raise ValueError("{name} must be an instance of {cls}"
                         .format(name=name, cls=base_class_name))
    return obj or default


def _initialize_models(obj, tokenizer, pos_tagger,
                       np_extractor, analyzer, parser, classifier):
    """Common initialization between BaseBlob and Blobber classes."""
    # tokenizer may be a textblob or an NLTK tokenizer
    obj.tokenizer = _validated_param(tokenizer, "tokenizer",
                                    base_class=(BaseTokenizer, nltk.tokenize.api.TokenizerI),
                                    default=BaseBlob.tokenizer,
                                    base_class_name="BaseTokenizer")
    obj.np_extractor = _validated_param(np_extractor, "np_extractor",
                                        base_class=BaseNPExtractor,
                                        default=BaseBlob.np_extractor)
    obj.pos_tagger = _validated_param(pos_tagger, "pos_tagger",
                                        BaseTagger, BaseBlob.pos_tagger)
    obj.analyzer = _validated_param(analyzer, "analyzer",
                                     BaseSentimentAnalyzer, BaseBlob.analyzer)
    obj.parser = _validated_param(parser, "parser", BaseParser, BaseBlob.parser)
    obj.classifier = classifier


class BaseBlob(StringlikeMixin, BlobComparableMixin):

    '''An abstract base class that all textblob classes will inherit from.
    Includes words, POS tag, NP, and word count properties. Also includes
    basic dunder and string methods for making objects like Python strings.

    :param text: A string.
    :param tokenizer: (optional) A tokenizer instance. If ``None``,
        defaults to :class:`WordTokenizer() <textblob.tokenizers.WordTokenizer>`.
    :param np_extractor: (optional) An NPExtractor instance. If ``None``,
        defaults to :class:`FastNPExtractor() <textblob.en.np_extractors.FastNPExtractor>`.
    :param pos_tagger: (optional) A Tagger instance. If ``None``,
        defaults to :class:`PatternTagger <textblob.en.taggers.PatternTagger>`.
    :param analyzer: (optional) A sentiment analyzer. If ``None``,
        defaults to :class:`PatternAnalyzer <textblob.en.sentiments.PatternAnalyzer>`.
    :param parser: A parser. If ``None``, defaults to
        :class:`PatternParser <textblob.en.parsers.PatternParser>`.
    :param classifier: A classifier.

    .. versionchanged:: 0.6.0
        ``clean_html`` parameter deprecated, as it was in NLTK.
    '''

    np_extractor = FastNPExtractor()
    pos_tagger = PatternTagger()
    tokenizer = WordTokenizer()
    translator = Translator()
    analyzer = PatternAnalyzer()
    parser = PatternParser()

    def __init__(self, text, tokenizer=None,
                pos_tagger=None, np_extractor=None, analyzer=None,
                parser=None, classifier=None, clean_html=False):
        if not isinstance(text, basestring):
            raise TypeError('The `text` argument passed to `__init__(text)` '
                            'must be a string, not {0}'.format(type(text)))
        if clean_html:
            raise NotImplementedError("clean_html has been deprecated. "
                                    "To remove HTML markup, use BeautifulSoup's "
                                    "get_text() function")
        self.raw = self.string = text
        self.stripped = lowerstrip(self.raw, all=True)
        _initialize_models(self, tokenizer, pos_tagger, np_extractor, analyzer,
                           parser, classifier)

    @cached_property
    def words(self):
        '''Return a list of word tokens. This excludes punctuation characters.
        If you want to include punctuation characters, access the ``tokens``
        property.
        '''
        return WordList(WordTokenizer().itokenize(self.raw, include_punc=False))

    @cached_property
    def tokens(self):
        '''Return a list of tokens, using this blob's tokenizer object
        (defaults to :class:`WordTokenizer <textblob.tokenizers.WordTokenizer>`).
        '''
        return WordList(self.tokenizer.tokenize(self.raw))

    def tokenize(self, tokenizer=None):
        '''Return a list of tokens, using ``tokenizer``.

        :param tokenizer: (optional) A tokenizer object. If None, defaults to
            this blob's default tokenizer.
        '''
        t = tokenizer if tokenizer is not None else self.tokenizer
        return WordList(t.tokenize(self.raw))

    def parse(self, parser=None):
        '''Parse the text.

        :param parser: (optional) A parser instance. If ``None``, defaults to
            this blob's default parser.

        .. versionadded:: 0.6.0
        '''
        p = parser if parser is not None else self.parser
        return p.parse(self.raw)

    def classify(self):
        '''Classify the blob using the blob's ``classifier``.'''
        if self.classifier is None:
            raise NameError("This blob has no classifier. Train one first!")
        return self.classifier.classify(self.raw)

    @cached_property
    def sentiment(self):
        '''Return a tuple of form (polarity, subjectivity ) where polarity
        is a float within the range [-1.0, 1.0] and subjectivity is a float
        within the range [0.0, 1.0] where 0.0 is very objective and 1.0 is
        very subjective.

        :rtype: tuple
        '''
        return self.analyzer.analyze(self.raw)

    @cached_property
    def polarity(self):
        '''Return the polarity score as a float within the range [-1.0, 1.0]

        :rtype: float
        '''
        return PatternAnalyzer().analyze(self.raw)[0]

    @cached_property
    def subjectivity(self):
        '''Return the subjectivity score as a float within the range [0.0, 1.0]
        where 0.0 is very objective and 1.0 is very subjective.

        :rtype: float
        '''
        return PatternAnalyzer().analyze(self.raw)[1]

    @cached_property
    def noun_phrases(self):
        '''Returns a list of noun phrases for this blob.'''
        return WordList([phrase.strip().lower()
                        for phrase in self.np_extractor.extract(self.raw)
                        if len(phrase) > 1])

    @cached_property
    def pos_tags(self):
        '''Returns an list of tuples of the form (word, POS tag).

        Example:
        ::

            [('At', 'IN'), ('eight', 'CD'), ("o'clock", 'JJ'), ('on', 'IN'),
                    ('Thursday', 'NNP'), ('morning', 'NN')]

        :rtype: list of tuples
        '''
        return [(Word(word, pos_tag=t), unicode(t))
                for word, t in self.pos_tagger.tag(self.raw)
                if not PUNCTUATION_REGEX.match(unicode(t))]

    tags = pos_tags

    @cached_property
    def word_counts(self):
        '''Dictionary of word frequencies in this text.
        '''
        counts = defaultdict(int)
        stripped_words = [lowerstrip(word) for word in self.words]
        for word in stripped_words:
            counts[word] += 1
        return counts

    @cached_property
    def np_counts(self):
        '''Dictionary of noun phrase frequencies in this text.
        '''
        counts = defaultdict(int)
        for phrase in self.noun_phrases:
            counts[phrase] += 1
        return counts

    def ngrams(self, n=3):
        '''Return a list of n-grams (tuples of n successive words) for this
        blob.
        '''
        if n <= 0:
            return []
        grams = [WordList(self.words[i:i+n])
                            for i in range(len(self.words) - n + 1)]
        return grams

    def translate(self, from_lang=None, to="en"):
        '''Translate the blob to another language.
        Uses the Google Translate API. Returns a new TextBlob.

        Requires an internet connection.

        Usage:
        ::

            >>> b = TextBlob("Simple is better than complex")
            >>> b.translate(to="es")
            TextBlob('Lo simple es mejor que complejo')

        Language code reference:
            https://developers.google.com/translate/v2/using_rest#language-params

        .. versionadded:: 0.5.0.

        :param from_lang: Language to translate from. If ``None``, will attempt
            to detect the language.
        :param to: Language to translate to.
        :rtype: BaseBlob

        '''
        if from_lang is None:
            from_lang = self.translator.detect(self.string)
        return self.__class__(self.translator.translate(self.raw,
                        from_lang=from_lang, to_lang=to))

    def detect_language(self):
        '''Detect the blob's language using the Google Translate API.

        Requires an internet connection.

        Usage:
        ::

            >>> b = TextBlob("bonjour")
            >>> b.detect_language()
            u'fr'

        Language code reference:
            https://developers.google.com/translate/v2/using_rest#language-params

        .. versionadded:: 0.5.0

        :rtype: str

        '''
        return self.translator.detect(self.raw)

    def correct(self):
        '''Attempt to correct the spelling of a blob.

        .. versionadded:: 0.6.0

        :rtype: BaseBlob
        '''
        tok = WordTokenizer()
        corrected = (Word(w).correct() for w in tok.tokenize(self.raw, include_punc=True))
        # Separate each token with a space unless the token is a punctuation
        ret = ''
        for i, word in enumerate(corrected):
            # Avoid an extra space at the beginning
            if word in pystring.punctuation or i == 0:
                ret = ''.join([ret, word])
            else:
                ret = ' '.join([ret, word])
        return self.__class__(ret)

    def _cmpkey(self):
        '''Key used by ComparableMixin to implement all rich comparison
        operators.
        '''
        return self.raw

    def _strkey(self):
        '''Key used by StringlikeMixin to implement string methods.'''
        return self.raw

    def __hash__(self):
        return hash(self._cmpkey())

    def __add__(self, other):
        '''Concatenates two text objects the same way Python strings are
        concatenated.

        Arguments:
        - `other`: a string or a text object
        '''
        if isinstance(other, basestring):
            return self.__class__(self.raw + other)
        elif isinstance(other, BaseBlob):
            return self.__class__(self.raw + other.raw)
        else:
            raise TypeError('Operands must be either strings or {0} objects'
                .format(self.__class__.__name__))

    def split(self, sep=None, maxsplit=sys.maxsize):
        """Behaves like the built-in str.split() except returns a
        WordList.
        """
        return WordList(self._strkey().split(sep, maxsplit))


class TextBlob(BaseBlob):

    """A general text block, meant for larger bodies of text (esp. those
    containing sentences). Inherits from :class:`BaseBlob <BaseBlob>`.

    :param text: A string.
    :param tokenizer: (optional) A tokenizer instance. If ``None``, defaults to
        :class:`WordTokenizer() <textblob.tokenizers.WordTokenizer>`.
    :param np_extractor: (optional) An NPExtractor instance. If ``None``,
        defaults to :class:`FastNPExtractor() <textblob.en.np_extractors.FastNPExtractor>`.
    :param pos_tagger: (optional) A Tagger instance. If ``None``, defaults to
        :class:`PatternTagger <textblob.en.taggers.PatternTagger>`.
    :param analyzer: (optional) A sentiment analyzer. If ``None``, defaults to
        :class:`PatternAnalyzer <textblob.en.sentiments.PatternAnalyzer>`.
    :param classifier: (optional) A classifier.
    """

    @cached_property
    def sentences(self):
        '''Return list of :class:`Sentence <Sentence>` objects.'''
        return self._create_sentence_objects()

    @cached_property
    def words(self):
        '''Return a list of word tokens. This excludes punctuation characters.
        If you want to include punctuation characters, access the ``tokens``
        property.
        '''
        # NLTK's word tokenizer expects sentences as input, so tokenize the
        # blob into sentences before tokenizing to words
        words = []
        for sent in self.sentences:
            words.extend(WordTokenizer().tokenize(sent.raw, include_punc=False))
        return WordList(words)

    @property
    def raw_sentences(self):
        '''List of strings, the raw sentences in the blob.'''
        return [sentence.raw for sentence in self.sentences]

    @property
    def serialized(self):
        '''Returns a list of each sentence's dict representation.'''
        return [sentence.dict for sentence in self.sentences]

    def to_json(self, *args, **kwargs):
        '''Return a json representation (str) of this blob.
        Takes the same arguments as json.dumps.

        .. versionadded:: 0.5.1
        '''
        return json.dumps(self.serialized, *args, **kwargs)

    @property
    def json(self):
        '''The json representation of this blob.

        .. versionchanged:: 0.5.1
            Made ``json`` a property instead of a method to restore backwards
            compatibility that was broken after version 0.4.0.
        '''
        return self.to_json()

    def _create_sentence_objects(self):
        '''Returns a list of Sentence objects given
        a list of sentence strings. Attempts to handle sentences that
        have more than one punctuation mark at the end of the sentence.
        Examples: "An ellipses is no problem..." or "This is awesome!!!"
        '''
        sent_tokenizer = SentenceTokenizer()
        sentence_objects = []
        sentences = sent_tokenizer.itokenize(self.raw)
        char_index = 0  # Keeps track of character index within the blob
        for sent in sentences:
            # Compute the start and end indices of the sentence
            # within the blob
            try:
                start_index = self.raw.index(sent, char_index)
                char_index += len(sent)
                end_index = start_index + len(sent)
            except ValueError:
                logger.warn("Detected sentence with multiple punctuation marks "
                            "at the end. This may make the start and end indices "
                            "inaccurate.")
                start_index = None
                end_index = None
                char_index = 0
            # Sentences share the same models as their parent blob
            s = Sentence(sent, start_index=start_index, end_index=end_index,
                tokenizer=self.tokenizer, np_extractor=self.np_extractor,
                pos_tagger=self.pos_tagger, analyzer=self.analyzer,
                parser=self.parser, classifier=self.classifier)
            sentence_objects.append(s)
        return sentence_objects


class Sentence(BaseBlob):

    '''A sentence within a TextBlob. Inherits from :class:`BaseBlob <BaseBlob>`.

    :param sentence: A string, the raw sentence.
    :param start_index: An int, the index where this sentence begins
                        in a TextBlob. If not given, defaults to 0.
    :param end_index: An int, the index where this sentence ends in
                        a TextBlob. If not given, defaults to the
                        length of the sentence - 1.
    '''

    def __init__(self, sentence, start_index=0, end_index=None, *args, **kwargs):
        super(Sentence, self).__init__(sentence, *args, **kwargs)
        self.start = self.start_index = start_index
        self.end = self.end_index = end_index or len(sentence) - 1

    @property
    def dict(self):
        '''The dict representation of this sentence.'''
        return {
            'raw': self.raw,
            'start_index': self.start_index,
            'end_index': self.end_index,
            'stripped': self.stripped,
            'noun_phrases': self.noun_phrases,
            'polarity': self.polarity,
            'subjectivity': self.subjectivity,
        }


class Blobber(object):

    '''A factory for TextBlobs that all share the same tagger,
    tokenizer, parser, classifier, and np_extractor.

    Usage:

        >>> from textblob import Blobber
        >>> from textblob.taggers import NLTKTagger
        >>> from textblob.tokenizers import SentenceTokenizer
        >>> tb = Blobber(pos_tagger=NLTKTagger(), tokenizer=SentenceTokenizer())
        >>> blob1 = tb("This is one blob.")
        >>> blob2 = tb("This blob has the same tagger and tokenizer.")
        >>> blob1.pos_tagger is blob2.pos_tagger
        True

    :param tokenizer: (optional) A tokenizer instance. If ``None``,
        defaults to :class:`WordTokenizer() <textblob.tokenizers.WordTokenizer>`.
    :param np_extractor: (optional) An NPExtractor instance. If ``None``,
        defaults to :class:`FastNPExtractor() <textblob.en.np_extractors.FastNPExtractor>`.
    :param pos_tagger: (optional) A Tagger instance. If ``None``,
        defaults to :class:`PatternTagger <textblob.en.taggers.PatternTagger>`.
    :param analyzer: (optional) A sentiment analyzer. If ``None``,
        defaults to :class:`PatternAnalyzer <textblob.en.sentiments.PatternAnalyzer>`.
    :param parser: A parser. If ``None``, defaults to
        :class:`PatternParser <textblob.en.parsers.PatternParser>`.
    :param classifier: A classifier.

    .. versionadded:: 0.4.0
    '''

    np_extractor = FastNPExtractor()
    pos_tagger = PatternTagger()
    tokenizer = WordTokenizer()
    analyzer = PatternAnalyzer()
    parser = PatternParser()

    def __init__(self, tokenizer=None, pos_tagger=None, np_extractor=None,
                analyzer=None, parser=None, classifier=None):
        _initialize_models(self, tokenizer, pos_tagger, np_extractor, analyzer,
                            parser, classifier)

    def __call__(self, text):
        '''Return a new TextBlob object with this Blobber's ``np_extractor``,
        ``pos_tagger``, ``tokenizer``, ``analyzer``, and ``classifier``.

        :returns: A new TextBlob.
        '''
        return TextBlob(text, tokenizer=self.tokenizer, pos_tagger=self.pos_tagger,
                        np_extractor=self.np_extractor, analyzer=self.analyzer,
                        parser=self.parser,
                        classifier=self.classifier)

    def __repr__(self):
        classifier_name = self.classifier.__class__.__name__ + "()" if self.classifier else "None"
        return ("Blobber(tokenizer={0}(), pos_tagger={1}(), "
                    "np_extractor={2}(), analyzer={3}(), parser={4}(), classifier={5})")\
                    .format(self.tokenizer.__class__.__name__,
                            self.pos_tagger.__class__.__name__,
                            self.np_extractor.__class__.__name__,
                            self.analyzer.__class__.__name__,
                            self.parser.__class__.__name__,
                            classifier_name)

    __str__ = __repr__
