from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler, \
    intent_file_handler
from mycroft.util.parse import match_one
from mycroft.audio import wait_while_speaking
from langcodes import standardize_tag, LanguageData, find_name
from restcountries import RestCountryApi
from money.money import CURRENCY
import requests
import json

__author__ = 'jarbas'


class CountriesSkill(MycroftSkill):

    def __init__(self):
        super(CountriesSkill, self).__init__()
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

    def initialize(self):
        for c in self.countries_data.keys():
            self.register_vocabulary("country", c)

    def pretty_currency(self, currency_code):
        currency_code = currency_code.upper()
        if currency_code in CURRENCY.keys():
            return CURRENCY[currency_code].name
        return currency_code

    # intent handlers
    # country is only populated by adapt context
    #@intent_handler(IntentBuilder("CountryRegion")
    #                .require("where").require("country")
    #                .require("adapt_trigger"))
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
            self.set_context("adapt_trigger")
            self.set_context("country", name)

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

    #@intent_handler(IntentBuilder("CountryCurrency")
    #                .require("currency").require("country")
    #                .require("question").require("adapt_trigger"))
    @intent_file_handler("country_currency.intent")
    def handle_country_currency(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        self.log.debug(country)
        if country in self.countries_data.keys():
            self.set_context("adapt_trigger")
            self.set_context("country", country)
            coins = self.countries_data[country]["currencies"]
            for c in coins:
                c = self.pretty_currency(c)
                self.speak(c)
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("country_in_region.intent")
    def handle_country_in_region(self, message):
        region = message.data["region"]
        self.log.debug(region)
        region, score = match_one(region, self.regions)

        if score > 0.5:
            countries = self.search_country_by_region(region)
        else:
            region, score = match_one(region, self.subregions)
            if score > 0.5:
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
        clean_up = ["is"] # words commonly caught by mistake in padatious
        language = message.data["language"]
        words = language.split(" ")
        language = " ".join([word for word in words if word not in clean_up])
        self.log.debug(language)
        lang_code = find_name('language', language, standardize_tag(self.lang))
        countries = self.search_country_by_language(lang_code)
        if len(countries):
            for c in countries:
                self.speak(c["name"])
        else:
            self.speak_dialog("bad_country")

    #@intent_handler(IntentBuilder("CountryLanguage")
    #                .require("languages").require("country")
    #                .require("question").require("adapt_trigger"))
    @intent_file_handler("country_languages.intent")
    def handle_country_languages(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        self.log.debug(country)
        if country in self.countries_data.keys():
            langs = self.countries_data[country]["languages"]
            for lang in langs:
                self.speak(lang)
                wait_while_speaking()
        else:
            self.speak_dialog("bad_country")

    #@intent_handler(IntentBuilder("CountryTimezone")
    #                .require("timezone").require("country")
    #                .require("adapt_trigger"))
    @intent_file_handler("country_timezones.intent")
    def handle_country_timezones(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        self.log.debug(country)
        if country in self.countries_data.keys():
            self.set_context("adapt_trigger")
            self.set_context("country", country)
            timezones = self.countries_data[country]["timezones"]
            for t in timezones:
                self.speak(t)
                wait_while_speaking()
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("country_area.intent")
    def handle_country_area(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        self.log.debug(country)
        if country in self.countries_data.keys():
            self.set_context("country", country)
            self.set_context("adapt_trigger")
            area = self.countries_data[country]["area"]
            # TODO units
            self.speak(area)
        else:
            self.speak_dialog("bad_country")

    #@intent_handler(IntentBuilder("CountryPopulation")
    #                .require("population").require("country")
    #                .require("question").require("adapt_trigger"))
    @intent_file_handler("country_population.intent")
    def handle_country_population(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        self.log.debug(country)
        if country in self.countries_data.keys():
            self.set_context("country", country)
            self.set_context("adapt_trigger")
            population = self.countries_data[country]["population"]
            self.speak(population)
        else:
            self.speak_dialog("bad_country")

    #@intent_handler(IntentBuilder("CountryBorders")
    #                .require("borders").require("country")
    #                .require("question").require("adapt_trigger"))
    @intent_file_handler("country_borders.intent")
    def handle_country_borders(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        self.log.debug(country)
        if country in self.countries_data.keys():
            self.set_context("country", country)
            self.set_context("adapt_trigger")
            borders = self.countries_data[country]["borders"]
            for b in borders:
                self.speak(self.country_codes[b])
                wait_while_speaking()
        else:
            self.speak_dialog("bad_country")

    #@intent_handler(IntentBuilder("CountryCapital")
     #               .require("capital").require("country")
     #               .require("question").require("adapt_trigger"))
    @intent_file_handler("country_capital.intent")
    def handle_country_capital(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        self.log.debug(country)
        if country in self.countries_data.keys():
            self.set_context("country", country)
            self.set_context("adapt_trigger")
            capital = self.countries_data[country]["capital"]
            self.speak(capital)
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("denonym.intent")
    def handle_country_denonym(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        country = message.data["country"]
        self.log.debug(country)
        if country in self.countries_data.keys():
            denonym = self.countries_data[country]["demonym"]
            self.speak(denonym)
            self.set_context("country", country)
            self.set_context("adapt_trigger")
        else:
            self.speak_dialog("bad_country")

    @intent_file_handler("country_num.intent")
    def handle_country_number(self, message):
        if not len(self.countries_data):
            self.get_country_data()
        self.speak_dialog("country_number",
                          {"number": len(self.countries_data)})

    # country api
    def get_all_countries(self):
        return CountryApi.get_all()

    def get_country_data(self):
        countries = self.get_all_countries()
        for c in countries:
            name = c["name"].lower()
            self.countries_data[name] = {}
            self.countries_data[name]["timezones"] = c["timezones"]
            self.countries_data[name]["demonym"] = c["demonym"]
            self.countries_data[name]["currencies"] = c["currencies"]
            self.countries_data[name]["alpha2Code"] = c["alpha2Code"]
            self.country_codes[c["alpha2Code"]] = name
            self.countries_data[name]["alpha3Code"] = c["alpha3Code"]
            self.country_codes[c["alpha3Code"]] = name
            self.countries_data[name]["area"] = str(c["area"])
            self.countries_data[name]["languages"] = [LanguageData(language=l)
                                                          .language_name()
                                                      for l in c["languages"]]
            self.countries_data[name]["lang_codes"] = [standardize_tag(l)
                                                       for l in
                                                       c["languages"]]
            self.countries_data[name]["capital"] = c["capital"]
            self.countries_data[name]["borders"] = c["borders"]
            self.countries_data[name]["nativeName"] = c["nativeName"]
            self.countries_data[name]["population"] = str(c["population"])
            self.countries_data[name]["region"] = c["region"]
            self.countries_data[name]["subregion"] = c["subregion"]
            if len(c["latlng"]):
                self.countries_data[name]["lat"], self.countries_data[name][
                    "long"] = c["latlng"]

    def search_country(self, name="portugal"):
        return CountryApi.get_countries_by_name(name)

    def search_country_by_code(self, code="ru"):
        return CountryApi.get_countries_by_country_codes([code])

    def search_country_by_language(self, lang_code="pt"):
        return CountryApi.get_countries_by_language(lang_code)

    def search_country_by_region(self, region="africa"):
        return CountryApi.get_countries_by_region(region)

    def search_country_by_subregion(self, subregion="western asia"):
        return CountryApi.get_countries_by_subregion(subregion)


class CountryApi(RestCountryApi):
    BASE_URI = 'https://restcountries.eu/rest/v1'
    QUERY_SEPARATOR = ','

    @classmethod
    def _get_country_list(cls, resource, term=''):
        # changed to return a dict instead of country object
        uri = '{}{}/{}'.format(cls.BASE_URI, resource, term)  # build URL
        response = requests.get(uri)
        if response.status_code == 200:
            result_list = []
            data = json.loads(response.text) # parse json to dict
            if type(data) == list:
                for country_data in data:
                    #country = Country(country_data)
                    result_list.append(country_data)
            else:
                #return Country(data)
                return data
            return result_list
        elif response.status_code == 404:
            raise requests.exceptions.InvalidURL
        else:
            raise requests.exceptions.RequestException


def create_skill():
    return CountriesSkill()

