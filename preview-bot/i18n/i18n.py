# -*- coding: utf-8 -*-
import collections
import rbtranslations

fallback_lang = 'en'

lang_dict = collections.OrderedDict(
    [('en', u'\U0001F1FA\U0001F1F8 English'), ('de',  u'\U0001F1E9\U0001F1EA Deutsch'),
     ('fa', u'\U0001F1EE\U0001F1F7 Farsi'), ('ru', u'\U0001F1F7\U0001F1FA Русский'),
     ('uz', u'\U0001F1FA\U0001F1FF Ўзбекча')])

# so that we can use the shortcut instead of the long language name (which cannot be displayed properly in botan)
inverse_lang_dict = {v: k for k, v in lang_dict.items()}


trs = {}
for lang_code in lang_dict.keys():
    trs[lang_code] = rbtranslations.translation('message', __file__, [lang_code])


def ugettext(lang, key):
    ret = key
    for l in [lang, fallback_lang]:
        try:
            ret = trs[l].ugettext(key).encode('utf-8')
        except KeyError:
            pass
        if ret != key:
            # if message not found, fallback to english, otherwise break
            break
    return ret
