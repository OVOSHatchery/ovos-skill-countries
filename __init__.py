from mycroft.util.parse import match_one
import langcodes
from restcountries import RestCountryApi
from money.money import CURRENCY
from lingua_franca.format import pronounce_number
import requests
import json
from tempfile import gettempdir
from os.path import join, isfile, expanduser
from padatious import IntentContainer

try:
    import matplotlib.pyplot as plt
    import cartopy
except ImportError:

    cartopy = None

from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel


class CountriesSkill(CommonQuerySkill):

    def __init__(self):
        super(CountriesSkill, self).__init__()
        if "map_style" not in self.settings:
            self.settings["map_style"] = "ortho"
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

        intent_cache = expanduser(
            self.config_core['padatious']['intent_cache'])

        self.intents = IntentContainer(intent_cache)

    def initialize(self):
        if cartopy is None:
            self.log.info(
                "Map plots are disabled, additional requirements needed")
            self.log.info(
                "https://scitools.org.uk/cartopy/docs/latest/installing.html")
        self.load_intents()

    # CommonQuery Padatious subparser
    def load_intents(self):
        for intent in ["country_area", "country_borders", "country_capital",
                       "country_currency", "country_in_region",
                       "country_languages", "country_num",
                       "country_population",
                       "country_region", "country_timezones", "denonym",
                       "where_language_spoken"]:
            path = self.find_resource(intent + '.intent', "vocab")
            if path:
                self.intents.load_intent(intent, path)

        self.intents.train(single_thread=True)

    def intent2answer(self, intent, data):
        # Get response from intents
        response = None
        if intent == "country_area":
            response = self.handle_country_area(data)
        elif intent == "country_timezones":
            response = self.handle_country_timezones(data)
        elif intent == "where_language_spoken":
            response = self.handle_language_where(data)
        elif intent == "denonym":
            response = self.handle_country_denonym(data)
        elif intent == "country_region":
            response = self.handle_country_where(data)
        elif intent == "country_population":
            response = self.handle_country_population(data)
        elif intent == "country_borders":
            response = self.handle_country_borders(data)
        elif intent == "country_capital":
            response = self.handle_country_capital(data)
        elif intent == "country_currency":
            response = self.handle_country_currency(data)
        elif intent == "country_in_region":
            response = self.handle_country_in_region(data)
        elif intent == "country_languages":
            response = self.handle_country_languages(data)
        elif intent == "country_num":
            response = self.handle_country_number(data)
        return response

    def CQS_match_query_phrase(self, phrase):
        """Analyze phrase to see if it is a play-able phrase with this skill.

                Needs to be implemented by the skill.

                Arguments:
                    phrase (str): User phrase, "What is an aardwark"

                Returns:
                    (match, CQSMatchLevel[, callback_data]) or None: Tuple containing
                         a string with the appropriate matching phrase, the PlayMatch
                         type, and optionally data to return in the callback if the
                         match is selected.
        """
        response = None
        match = self.intents.calc_intent(phrase)
        level = CQSMatchLevel.CATEGORY
        data = match.matches
        intent = match.name
        score = match.conf
        data["intent"] = intent
        data["score"] = score

        if score > 0.8:
            level = CQSMatchLevel.EXACT
        elif score > 0.5:
            level = CQSMatchLevel.CATEGORY
        elif score > 0.3:
            level = CQSMatchLevel.GENERAL
        else:
            intent = None

        if intent:
            # Validate extracted entities
            country = data.get("country")
            region = data.get("region")
            language = data.get("language")

            if country:
                data["query"] = country
                # ensure we really have a country name
                response = self.dialog_renderer.render("bad_country", {})
                match, score = match_one(country.lower(),
                                         list(self.countries_data.keys()))
                self.log.debug(
                    "Country fuzzy match: {n}, Score: {s}".format(n=match,
                                                                  s=score))
                if score > 0.5:
                    country = match
                    data.update(self.countries_data[country])
                else:
                    countries = self.search_country(country)
                    if not len(countries) > 0:
                        level = CQSMatchLevel.GENERAL
                    else:
                        country = countries[0]["name"]
                        data.update(countries[0])
                        # TODO disambiguation
                        if len(countries) > 1:
                            data["disambiguation"] = countries[1:]
                            self.log.debug("multiple matches found: " +
                                           str([c["name"] for c in countries]))
                data["country"] = country  # normalized from match

            if language:
                data["query"] = language
                # ensure we really have a language name
                words = language.split(" ")
                clean_up = ["is"]
                # remove words commonly caught by mistake in padatious
                language = " ".join(
                    [word for word in words if word not in clean_up])
                lang_code = langcodes.find_name('language',
                                                language,
                                                langcodes.standardize_tag(
                                                    self.lang))
                lang_code = str(lang_code)
                self.log.debug("Detected lang code: " + lang_code)
                if not lang_code:
                    return None
                data["lang_code"] = lang_code
                # TODO
                countries = self.search_country_by_language(lang_code)
                data["country_list"] = countries

            if region:
                data["query"] = region
                # ensure we really have a region name
                response = self.dialog_renderer.render("bad_region")
                countries = None
                match, score = match_one(region, self.regions)
                data["region_score"] = score

                if score > 0.5:
                    region = match
                    countries = self.search_country_by_region(region)

                match, score2 = match_one(region, self.subregions)
                data["subregion_score"] = score2
                if score2 > score:
                    region = match
                    countries = self.search_country_by_subregion(region)

                if score > 0.8 and not country:
                    level = CQSMatchLevel.EXACT
                elif score > 0.5 and not country:
                    level = CQSMatchLevel.CATEGORY
                elif score > 0.3 and not country:
                    level = CQSMatchLevel.GENERAL

                data["region"] = region
                self.log.debug("Detected region: " + region)
                data["country_list"] = countries

            # Get response from intents
            response = self.intent2answer(intent, data) or response

            if response:
                return (phrase, level, response, data)
        return None

    def CQS_action(self, phrase, data):
        """Take additional action IF the skill is selected.

        The speech is handled by the common query but if the chosen skill
        wants to display media, set a context or prepare for sending
        information info over e-mail this can be implemented here.

        Args:
            phrase (str): User phrase uttered after "Play", e.g. "some music"
            data (dict): Callback data specified in match_query_phrase()
        """
        self.settings["map_style"] = "cart"

        projection = cartopy.crs.PlateCarree()
        if data.get("country"):
            title = data["country"]
            if self.settings["map_style"] == "ortho":
                country = self.countries_data[data["country"].lower()]
                lat = country["lat"]
                lon = country["long"]
                projection = cartopy.crs.Orthographic(lon, lat)

            image = self.plot_country(data["country"], projection=projection)
            self.gui.show_image(image,
                                fill='PreserveAspectFit',
                                title=title)
        elif data.get("region"):
            title = data["region"]
            countries = data["country_list"]
            if self.settings["map_style"] == "ortho":
                country = self.countries_data[countries[0]["name"].lower()]
                lat = country["lat"]
                lon = country["long"]
                projection = cartopy.crs.Orthographic(lon, lat)

            image = self.plot_region(data["region"], projection=projection)
            self.gui.show_image(image,
                                fill='PreserveAspectFit',
                                title=title)

        elif data.get("country_list"):

            countries = data["country_list"]
            if self.settings["map_style"] == "ortho":
                country = self.countries_data[countries[0]["name"].lower()]
                lat = country["lat"]
                lon = country["long"]
                projection = cartopy.crs.Orthographic(lon, lat)

            title = data.get("region") \
                    or data.get("language") \
                    or data.get("lang_code") \
                    or " "
            countries = [c["name"] for c in countries]
            image = self.plot_countries(countries,
                                        projection=projection,
                                        name=title, region=data.get("region"))
            self.gui.show_image(image, fill='PreserveAspectFit', title=title,
                                caption = ", ".join(countries))

    # gui
    @staticmethod
    def _get_country_geometry(query, region=None, min_score=0.7):
        best_score = 0
        best_match = None

        shapename = 'admin_0_countries'
        countries_shp = cartopy.io.shapereader.natural_earth(
            resolution='110m',
            category='cultural',
            name=shapename)

        for country in cartopy.io.shapereader.Reader(
                countries_shp).records():
            country_name = country.attributes['NAME'].lower()
            country_long_name = country.attributes['NAME_LONG'].lower()

            reg = country.attributes["REGION_WB"].lower()
            subregion = country.attributes["SUBREGION"].lower()
            continent = country.attributes["CONTINENT"].lower()

            match, score = match_one(query.lower(),
                                     [country_long_name, country_name])

            if region:
                _, score2 = match_one(region.lower(),
                                      [reg, subregion, continent])
                score = (score + score2) / 2

            if score > best_score:
                best_score = score
                best_match = country.geometry

        if best_score < min_score:
            best_match = None    

        return best_match

    def _get_region_countries(self, query, min_score=0.7):
        countries = []
        region, score = match_one(query, self.regions)

        if score > min_score - 0.15:
            countries = self.search_country_by_region(region)
        if score < min_score:
            region, score = match_one(query, self.subregions)
            if score > min_score:
                countries = self.search_country_by_subregion(region)

        return [c["name"] for c in countries]

    @staticmethod
    def _get_region_geometries(query, min_score=0.8):
        shapename = 'admin_0_countries'
        countries_shp = cartopy.io.shapereader.natural_earth(
            resolution='110m',
            category='cultural',
            name=shapename)
        geoms = []
        for country in cartopy.io.shapereader.Reader(
                countries_shp).records():
            continent = country.attributes["CONTINENT"].lower()
            region = country.attributes["REGION_WB"].lower()
            subregion = country.attributes["SUBREGION"].lower()

            match, score = match_one(query.lower(),
                                     [region, subregion, continent])

            if score > min_score or \
                    (query.lower() in region.lower() and score >= 0.5):
                geoms.append(country.geometry)
        return geoms

    def plot_country(self, query, projection=None, rgb=None):
        if cartopy is None:
            return

        output = join(gettempdir(),
                      query + self.settings["map_style"] + ".png")
        if isfile(output):
            return output

        ax = plt.axes(projection=projection)
        ax.stock_img()
        ax.coastlines()

        r, g, b = rgb or (255, 0, 0)
        color = (r / 255, g / 255, b / 255)

        geometry = self._get_country_geometry(query)
        if geometry:
            geometries = [geometry]
            ax.add_geometries(geometries,
                              cartopy.crs.PlateCarree(),
                              facecolor=color)
    
            plt.savefig(output, bbox_inches='tight', facecolor="black")
            plt.close()
            return output
        return None

    def plot_countries(self, countries, projection=None, rgb=None,
                       name=None, region=None):
        if cartopy is None:
            return
        name = name or "_".join([c[:2] for c in countries])

        output = join(gettempdir(), name + self.settings["map_style"] +
                      "_countries.png")

        if isfile(output):
            return output

        projection = projection or cartopy.crs.PlateCarree()

        ax = plt.axes(projection=projection)
        ax.stock_img()
        ax.coastlines()

        r, g, b = rgb or (255, 0, 0)
        color = (r / 255, g / 255, b / 255)

        geometries = []
        for query in countries:
            geometry = self._get_country_geometry(query, region)
            if geometry:
                geometries.append(geometry)

        ax.add_geometries(geometries,
                          cartopy.crs.PlateCarree(),
                          facecolor=color)

        plt.savefig(output, bbox_inches='tight', facecolor="black")
        plt.close()
        return output

    def plot_region(self, query, projection=None, rgb=None):
        if cartopy is None:
            return

        output = join(gettempdir(),
                      query + self.settings["map_style"] + "_region.png")
        if isfile(output):
            return output

        ax = plt.axes(projection=projection)
        ax.stock_img()
        ax.coastlines()

        r, g, b = rgb or (255, 0, 0)
        color = (r / 255, g / 255, b / 255)

        geometries = self._get_region_geometries(query)
        if not geometries:
            countries = self._get_region_countries(query)
            return self.plot_countries(countries, projection, (r,g,b),
                                       name=query, region=query)
        ax.add_geometries(geometries,
                          cartopy.crs.PlateCarree(),
                          facecolor=color)

        plt.savefig(output, bbox_inches='tight', facecolor="black")
        plt.close()
        return output

    # intents
    def handle_country_where(self, data):
        name = data["country"]
        region = data["region"]
        sub = data["subregion"]
        if region in sub:
            r = sub
        else:
            r = sub + ", " + region
        return self.dialog_renderer.render("country_location",
                                           {"country": name, "region": r})

    def handle_country_currency(self, data):
        country = data["country"]
        coins = self.countries_data[country]["currencies"]
        coins = ", ".join([self.pretty_currency(c) for c in coins])
        return self.dialog_renderer.render("currency",
                                           {"country": country, "coin": coins})

    def handle_country_in_region(self, data):
        region = data["region"]
        countries = data["country_list"]

        if len(countries):
            return "; ".join([c["name"] for c in countries])

        else:
            return self.dialog_renderer.render("bad_region")

    def handle_language_where(self, data):
        lang_code = data["lang_code"]
        lang_name = data["language"]
        countries = data["country_list"]
        if len(countries):
            # TODO dialog files
            return ", ".join([c["name"] for c in countries])
        else:
            return self.dialog_renderer.render("bad_country")

    def handle_country_languages(self, data):
        country = data["country"]
        if country in self.countries_data.keys():
            langs = self.countries_data[country]["languages"]
            return ", ".join([lang for lang in langs])
        else:
            return self.dialog_renderer.render("bad_country")

    def handle_country_timezones(self, data):
        country = data["country"]
        if country in self.countries_data.keys():
            timezones = ", ".join(self.countries_data[country]["timezones"])
            return self.dialog_renderer.render("timezones",
                                               {"country": country,
                                                "timezones": timezones})
        else:
            return self.dialog_renderer.render("bad_country")

    def handle_country_area(self, data):
        country = data["country"]
        if country in self.countries_data.keys():
            area = self.countries_data[country]["area"]
            # TODO convert units
            area = pronounce_number(float(area), lang=self.lang)
            return self.dialog_renderer.render("area",
                                               {"country": country,
                                                "number": area})
        else:
            return self.dialog_renderer.render("bad_country")

    def handle_country_population(self, data):
        country = data["country"]
        if country in self.countries_data.keys():
            population = self.countries_data[country]["population"]
            area = pronounce_number(int(population), lang=self.lang)
            return self.dialog_renderer.render("population",
                                               {"country": country,
                                                "number": area})
        else:
            return self.dialog_renderer.render("bad_country")

    def handle_country_borders(self, data):
        country = data["country"]
        if country in self.countries_data.keys():
            borders = self.countries_data[country]["borders"]
            borders = ", ".join([self.country_codes[b] for b in borders])
            return self.dialog_renderer.render("borders", {"country": country,
                                                           "borders": borders})
        else:
            return self.dialog_renderer.render("bad_country")

    def handle_country_capital(self, data):
        country = data["country"]
        if country in self.countries_data.keys():
            capital = self.countries_data[country]["capital"]
            return self.dialog_renderer.render("capital",
                                               {"country": country,
                                                "capital": capital})
        else:
            return self.dialog_renderer.render("bad_country")

    def handle_country_denonym(self, data):
        country = data["country"]
        if country in self.countries_data.keys():
            denonym = self.countries_data[country]["demonym"]
            return self.dialog_renderer.render("denonym",
                                               {"country": country,
                                                "denonym": denonym})

        else:
            return self.dialog_renderer.render("bad_country")

    def handle_country_number(self, data):
        number = pronounce_number(len(self.countries_data), lang=self.lang)
        return self.dialog_renderer.render("country_number",
                                           {"number": number})

    # country api
    @staticmethod
    def pretty_currency(currency_code):
        currency_code = currency_code.upper()
        if currency_code in CURRENCY.keys():
            return CURRENCY[currency_code].name
        return currency_code

    @staticmethod
    def get_all_countries():
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
            self.countries_data[name]["languages"] = [
                langcodes.LanguageData(language=l).language_name() for l in
                c["languages"]]
            self.countries_data[name]["lang_codes"] = [
                langcodes.standardize_tag(l) for l in c["languages"]]
            self.countries_data[name]["capital"] = c["capital"]
            self.countries_data[name]["borders"] = c["borders"]
            self.countries_data[name]["nativeName"] = c["nativeName"]
            self.countries_data[name]["population"] = str(c["population"])
            self.countries_data[name]["region"] = c["region"]
            self.countries_data[name]["subregion"] = c["subregion"]
            if len(c["latlng"]):
                self.countries_data[name]["lat"], \
                self.countries_data[name]["long"] = c["latlng"]

    @staticmethod
    def search_country(name):
        try:
            return CountryApi.get_countries_by_name(name)
        except:
            return []

    @staticmethod
    def search_country_by_code(code):
        try:
            return CountryApi.get_countries_by_country_codes([code])
        except:
            return []

    @staticmethod
    def search_country_by_language(lang_code):
        try:
            return CountryApi.get_countries_by_language(lang_code)
        except:
            return []

    @staticmethod
    def search_country_by_region(region):
        try:
            return CountryApi.get_countries_by_region(region)
        except:
            return []

    @staticmethod
    def search_country_by_subregion(subregion):
        try:
            return CountryApi.get_countries_by_subregion(subregion)
        except:
            return []


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
            data = json.loads(response.text)  # parse json to dict
            if type(data) == list:
                for country_data in data:
                    # country = Country(country_data)
                    result_list.append(country_data)
            else:
                # return Country(data)
                return data
            return result_list
        elif response.status_code == 404:
            raise requests.exceptions.InvalidURL
        else:
            raise requests.exceptions.RequestException


def create_skill():
    return CountriesSkill()
