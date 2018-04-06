from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler, \
    intent_file_handler
from langcodes import standardize_tag, LanguageData, find_name
import unirest
import json

__author__ = 'jarbas'


class CountriesSkill(MycroftSkill):

    def __init__(self):
        super(CountriesSkill, self).__init__()
        if "key" not in self.settings:
            # you are welcome, else get yours here
            # https://market.mashape.com/explore?sort=developers
            self.settings["key"] = \
                "mX8W7sqzonmshpIlUSgcf4VS2nzNp1dObQYjsniJyZlq3F2RBD"
        self.countries_data = {}
        self.country_codes = {}
        self.regions = [u'Asia', u'Europe', u'Africa', u'Oceania',
                        u'Americas', u'Polar']
        self.subregions = [u'Southern Asia', u'Northern Europe',
                           u'Southern Europe', u'Northern Africa',
                           u'Polynesia', u'Middle Africa', u'Caribbean',
                           u'South America', u'Western Asia',
                           u'Australia and New Zealand', u'Western Europe',
                           u'Eastern Europe', u'Central America',
                           u'Western Africa', u'Northern America',
                           u'Southern Africa', u'Eastern Africa',
                           u'South-Eastern Asia', u'Eastern Asia',
                           u'Melanesia', u'Micronesia', u'Central Asia']
        self.get_country_data()

    # intent handlers
    # country is only populated by adapt context
    @intent_handler(IntentBuilder("CountryRegion")
                    .require("where").require("country"))
    # padatious is the official handler
    @intent_file_handler("country_region.intent")
    def handle_country_where(self, message):
        country = message.data["country"]
        countries = self.search_country(country)
        if len(countries):
            # TODO did you mean this or that
            self.log.debug("multiple matches found: " +
                          str([c["name"] for c in countries]))
            c = countries[0]
            name = c["name"]
            region = c["region"]
            sub = c["subregion"]
            if region in sub:
                r = sub
            else:
                r = sub + ", " + region
            self.speak_dialog("country_location",
                              {"country": name, "region": r})
        else:
            self.speak_dialog("bad_country")

    @intent_handler(IntentBuilder("CountryCurrency")
                    .require("currency").require("country")
                    .require("question"))
    @intent_file_handler("country_currency.intent")
    def handle_country_currency(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        if country in self.countries_data.keys():
            coins = self.countries_data[country]["currencies"]
            for c in coins:
                # TODO currency code to spoken currency name
                self.speak(c)
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("country_in_region.intent")
    def handle_country_in_region(self, message):
        region = message.data["region"]
        if region in self.regions:
            countries = self.search_country_by_region(region)
        elif region in self.subregions:
            countries = self.search_country_by_subregion(region)
        else:
            self.speak_dialog("bad_region")
            return
        if len(countries):
            for c in countries:
                self.speak(c["name"])
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("where_language_spoken.intent")
    def handle_language_where(self, message):
        language = message.data["language"]
        lang_code = find_name('language', language, standardize_tag(self.lang))
        countries = self.search_country_by_language(lang_code)
        if len(countries):
            for c in countries:
                self.speak(c["name"])
        else:
            self.speak_dialog("bad_country")

    @intent_handler(IntentBuilder("CountryLanguage")
                    .require("languages").require("country")
                    .require("question"))
    @intent_file_handler("country_languages.intent")
    def handle_country_languages(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        if country in self.countries_data.keys():
            langs = self.countries_data[country]["languages"]
            for lang in langs:
                self.speak(lang)
        else:
            self.speak_dialog("bad_country")

    @intent_handler(IntentBuilder("CountryTimezone")
                    .require("timezone").require("country"))
    @intent_file_handler("country_timezones.intent")
    def handle_country_timezones(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        if country in self.countries_data.keys():
            self.set_context("country", country)
            timezones = self.countries_data[country]["timezones"]
            for t in timezones:
                self.speak(t)
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("country_area.intent")
    def handle_country_area(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        if country in self.countries_data.keys():
            self.set_context("country", country)
            area = self.countries_data[country]["area"]
            # TODO units
            self.speak(area)
        else:
            self.speak_dialog("bad_country")

    @intent_handler(IntentBuilder("CountryPopulation")
                    .require("population").require("country")
                    .require("question"))
    @intent_file_handler("country_population.intent")
    def handle_country_population(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        if country in self.countries_data.keys():
            self.set_context("country", country)
            population = self.countries_data[country]["population"]
            self.speak(population)
        else:
            self.speak_dialog("bad_country")

    @intent_handler(IntentBuilder("CountryBorders")
                    .require("borders").require("country")
                    .require("question"))
    @intent_file_handler("country_borders.intent")
    def handle_country_borders(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        if country in self.countries_data.keys():
            self.set_context("country", country)
            borders = self.countries_data[country]["borders"]
            for b in borders:
                self.speak(self.country_codes[b])
        else:
            self.speak_dialog("bad_country")

    @intent_handler(IntentBuilder("CountryCapital")
                    .require("capital").require("country")
                    .require("question"))
    @intent_file_handler("country_capital.intent")
    def handle_country_capital(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        if country in self.countries_data.keys():
            self.set_context("country", country)
            capital = self.countries_data[country]["capital"]
            self.speak(capital)
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("denonym.intent")
    def handle_country_denonym(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        if country in self.countries_data.keys():
            denonym = self.countries_data[country]["denonym"]
            self.speak(denonym)
            self.set_context("country", country)
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("country_num.intent")
    def handle_country_number(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        self.speak_dialog("country_number",
                          {"number": len(self.countries_data)})

    # mashape methods
    def get_mashape(self, url, headers=None):
        """
        generic mashape request method, provides api key in headers
        amd parses result accounting for possible encoding errors
        """
        headers = headers or {
            "X-Mashape-Key": self.settings["key"],
            "Accept": "application/json"
        }
        response = unirest.get(url,
                               headers=headers
                               )
        result = response.body
        if not isinstance(result, dict):
            result = json.loads(result.decode("utf-8", "ignore"))
        return result

    # mashape country api
    def get_all_countries(self):
        url = "https://restcountries-v1.p.mashape.com/all"
        response = self.get_mashape(url)
        return response

    def get_country_data(self):
        countries = self.get_all_countries()
        for c in countries:
            name = c["name"]
            self.countries_data[name] = {}
            self.countries_data[name]["timezones"] = c["timezones"]
            self.countries_data[name]["demonym"] = c["demonym"]
            self.countries_data[name]["currencies"] = c["currencies"]
            self.countries_data[name]["alpha2Code"] = c["alpha2Code"]
            self.country_codes[c["alpha2Code"]] = name
            self.countries_data[name]["alpha3Code"] = c["alpha3Code"]
            self.country_codes[c["alpha3Code"]] = name
            self.countries_data[name]["area"] = c["area"]
            self.countries_data[name]["languages"] = [LanguageData(language=l)
                                                          .language_name()
                                                      for l in c["languages"]]
            self.countries_data[name]["lang_codes"] = [standardize_tag(l)
                                                       for l in
                                                       c["languages"]]
            self.countries_data[name]["capital"] = c["capital"]
            self.countries_data[name]["borders"] = c["borders"]
            self.countries_data[name]["nativeName"] = c["nativeName"]
            self.countries_data[name]["population"] = c["population"]
            self.countries_data[name]["region"] = c["region"]
            self.countries_data[name]["subregion"] = c["subregion"]
            if len(c["latlng"]):
                self.countries_data[name]["lat"], self.countries_data[name][
                    "long"] = c["latlng"]

    def search_country(self, name="portugal"):
        url = "https://restcountries-v1.p.mashape.com/name/" + name
        response = self.get_mashape(url)
        return response

    def search_country_by_code(self, code="ru"):
        url = "https://restcountries-v1.p.mashape.com/alpha/" + code
        response = self.get_mashape(url)
        return response

    def search_country_by_language(self, lang_code="pt"):
        url = "https://restcountries-v1.p.mashape.com/lang/" + lang_code
        response = self.get_mashape(url)
        return response

    def search_country_by_region(self, region="africa"):
        url = "https://restcountries-v1.p.mashape.com/region/" + region
        response = self.get_mashape(url)
        return response

    def search_country_by_subregion(self, sub_region="western asia"):
        url = "https://restcountries-v1.p.mashape.com/subregion/" + \
              sub_region
        response = self.get_mashape(url)
        return response


def create_skill():
    return CountriesSkill()
