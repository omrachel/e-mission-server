import logging
import emission.storage.timeseries.timequery as estt
import emission.storage.timeseries.tcquery as esttc
import emission.storage.timeseries.geoquery as estg

import emission.storage.decorations.analysis_timeseries_queries as esda
import emission.storage.timeseries.abstract_timeseries as esta

def get_timeline_from_dt(user_id, start_local_dt, end_local_dt):
    logging.info("About to query for %s -> %s" % (start_local_dt, end_local_dt))

    places_entries = esda.get_entries(esda.RAW_PLACE_KEY, user_id,
        esttc.TimeComponentQuery("data.enter_local_dt", start_local_dt, end_local_dt))
    trips_entries = esda.get_entries(esda.RAW_TRIP_KEY, user_id,
        esttc.TimeComponentQuery("data.start_local_dt", start_local_dt, end_local_dt))

    for place in places_entries:
        logging.debug("Considering place %s: %s -> %s " %
                      (place.get_id(), place.data.enter_fmt_time, place.data.exit_fmt_time))
    for trip in trips_entries:
        logging.debug("Considering trip %s: %s -> %s " %
                      (trip.get_id(), trip.data.start_fmt_time, trip.data.end_fmt_time))

    return Timeline(places_entries, trips_entries)

def get_timeline(user_id, start_ts, end_ts):
    """
    Return a timeline of the trips and places from this start timestamp to this end timestamp.
    Note that each place and each trip has *two* associated timestamps, so we need to define which trips need to be
    returned. Right now, we define this as all places that are entered and all trips that are started within the
    specified time frame. Note that this means that, by definition, this may not include the starting and ending places
    for all trips, which is something that we need for our visualization. But we don't want the timeline to be
    visualization specific.
    Let's compromise by adding method to fill in start and end places which we will call if the timeline is used
    for visualization and not if not. This also means that we can use the id map to avoid duplicates in case the
    place does exist.
    :param user_id: the user whose timeline we are considering
    :param start_ts: the starting timestamp. we will include all places and trips that start after this.
    :param end_ts: the ending timestamp. we will include all places and trips that end after this.
    :return: a timeline object
    """
    places_entries = esda.get_entries(esda.RAW_PLACE_KEY, user_id=None,
                                      time_query=estt.TimeQuery("data.enter_ts",
                                                                start_ts, end_ts))
    trips_entries = esda.get_entries(esda.RAW_TRIP_KEY, user_id=None,
                                     time_query=estt.TimeQuery("data.start_ts",
                                                               start_ts, end_ts))
    for place in places_entries:
        logging.debug("Considering place %s: %s -> %s " % (place.get_id(),
                        place.data.enter_fmt_time, place.data.exit_fmt_time))
    for trip in trips_entries:
        logging.debug("Considering trip %s: %s -> %s " % (trip.get_id(),
                        trip.data.start_fmt_time, trip.data.end_fmt_time))

    return Timeline(places_entries, trips_entries)



def get_aggregate_timeline_from_dt(start_local_dt, end_local_dt, geojson=None):
    logging.info("About to query for %s -> %s in %s" % (start_local_dt, end_local_dt, geojson))

    if geojson is not None:
        place_gq = estg.GeoQuery(loc_field_list = ['data.location'], poly_region = geojson)
        trip_gq = estg.GeoQuery(loc_field_list = ['data.start_loc', 'data.end_loc'], poly_region = geojson)
    else:
        place_gq = None
        trip_gq = None

    ts = esta.TimeSeries.get_aggregate_time_series()
    places_entries = ts.find_entries("segmentation/raw_place",
        esttc.TimeComponentQuery("data.enter_local_dt", start_local_dt, end_local_dt),
        place_gq)
    trips_entries = ts.find_entries("segmentation/raw_place",
        esttc.TimeComponentQuery("data.start_local_dt", start_local_dt, end_local_dt),
        trip_gq)

    for place in places_entries:
        logging.debug("Considering place %s: %s -> %s " % (place.get_id(),
                                                           place.data.enter_fmt_time,
                                                           place.data.exit_fmt_time))
    for trip in trips_entries:
        logging.debug("Considering trip %s: %s -> %s " % (trip.get_id(),
                                                          trip.data.start_fmt_time,
                                                          trip.data.end_fmt_time))

    return Timeline(places_entries, trips_entries)


class Timeline(object):

    class State(object):
        def __init__(self, type, element):
            self.element_type = type
            self.element = element
            if element is None:
                self.id = None
            else:
                self.id = element.get_id()


    def __init__(self, places_or_stops_entries, trips_or_sections_entries):
        logging.debug("len(places) = %s, len(trips) = %s" %
                      (len(places_or_stops_entries), len(trips_or_sections_entries)))
        self.places = places_or_stops_entries
        self.trips = trips_or_sections_entries
        self.id_map = dict((p.get_id(), p) for p in self.places)
        self.id_map.update(dict((t.get_id(), t) for t in self.trips))

        if (len(self.places) == 0) and (len(self.trips) == 0):
            self.state = Timeline.State("none", None)
        elif len(self.places) == 0:
                self.state = Timeline.State("trip", self.trips[0])
        elif len(self.trips) == 0:
                self.state = Timeline.State("place", self.places[0])
        else:
            assert (len(self.places) > 0 and len(self.trips) > 0)
            if self.places[0].data.exit_ts < self.trips[0].data.start_ts:
                self.state = Timeline.State("place", self.places[0])
            else:
                self.state = Timeline.State("trip", self.trips[0])
        logging.debug("Starting with element of type %s, id %s, details %s" %
                      (self.state.element_type, self.state.id, self.state.element))

    def fill_start_end_places(self):
        """
        Must be called before we start iterating over the values. If this is called in the middle of the iteration,
        the results are undefined. In particular, they will be different depending on whether it was called when we
        were iterating over a place versus a trip.
        :return: None. The timeline is updated with the start and end place.
        """
        if len(self.trips) > 0:
            logging.debug("len(trips) = %s, adding start_place %s and end_place %s" % (len(self.trips),
                                                                                       self.trips[0].start_place,
                                                                                       self.trips[-1].end_place))
            start_place = self._addIfNotExists(self.trips[0].start_place)
            end_place = self._addIfNotExists(self.trips[-1].end_place)
            self.state = Timeline.State("place", start_place)  # Since this has been called before the iteration start

    def get_object(self, element_id):
        """
        Return the object corresponding to the id from the in-memory map. This should be more efficient than
        going to the database.
        :param element_id: the id for which we want to retrieve the element
        :return: the matching object
        """
        return self.id_map[element_id]

    def _addIfNotExists(self, place_id):
        """
        Adds the place specified by the given place_id to the place list and the place map and returns it
        :param place_id:
        :return:
        """
        import emission.storage.decorations.place_queries as esdp

        if place_id not in self.id_map:
            logging.debug("place id %s is not in the map, searching in database" % place_id)
            place_entry = esda.get_entry(esda.RAW_PLACE_KEY, place_id)
            self.places.append(place_entry)
            self.id_map[place_id] = place_entry
            logging.debug("retrieved object %s and added to id_map" % place_entry)
            return place_entry
        else:
            return self.id_map[place_id]


    def __iter__(self):
        return self

    def next(self):
        ret_val = self.state.element
        # logging.debug("ret_val = %s" % ret_val)
        if ret_val is None:
            # logging.info("ret_val is None, raising StopIteration")
            raise StopIteration
        # This is thread safe since there is no defined way to mutate the
        # curr_element outside of move_to_next(), adn move_to_next() is
        # synchronous, so this call will complete before it returns.
        self.move_to_next()
        return ret_val

    def move_to_next(self):
        # TODO: restructure the data model to avoid this stupid if/then.
        # e.g. rename field to be "starting" for both trip and section
        if self.state.element_type == "place":
            if hasattr(self.state.element, "starting_trip"):
                new_id = self.state.element.starting_trip
            else:
                assert(hasattr(self.state.element, "starting_section"))
                new_id = self.state.element.starting_section
            new_type = "trip"
        else:
            assert(self.state.element_type == "trip")
            if hasattr(self.state.element, "end_place"):
                new_id = self.state.element.end_place
            else:
                assert(hasattr(self.state.element, "end_stop"))
                new_id = self.state.element.end_stop
            new_type = "place"

        if new_id is None:
            self.state = Timeline.State("unknown", None)
        else:
            self.state = Timeline.State(new_type, self.id_map[new_id])
