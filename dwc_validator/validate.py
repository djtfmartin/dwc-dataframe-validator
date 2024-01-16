"""
This module contains functions for validating a pandas DataFrame containing Darwin Core data.
"""

import logging
from typing import List
import numpy
import requests
import json
import pandas as pd
from pandas import DataFrame
from dwc_validator.breakdown import field_populated_counts
from dwc_validator.model import DFValidationReport, CoordinatesReport, VocabularyReport, TaxonReport
from dwc_validator.vocab import basis_of_record_vocabulary, geodetic_datum_vocabulary, taxon_terms, name_matching_terms
from dwc_validator.vocab import required_columns_spatial_vocab,required_columns_other
from dwc_validator.vocab import required_taxonomy_columns

def validate_occurrence_dataframe(
        dataframe: DataFrame,
        id_fields: List[str] = None,
        id_term: str = "") -> DFValidationReport:
    """
    Validate a pandas DataFrame containing occurrence data.
    :param dataframe: the data frame to validate
    :param id_fields: fields used to specify a unique identifier for the record
    :param id_term: the actual darwin core term used for the id field e.g. occurrenceID, catalogNumber
    :return:
    """

    errors = []
    warnings = []

    # check id field are fully populated
    record_error_count = check_id_fields(id_fields, id_term, dataframe, errors)

    # check numeric fields have numeric values
    validate_numeric_fields(dataframe, warnings)

    # check for required columns
    all_required_columns_present = False
    missing_columns=[]

    # check taxonomic information supplied - create warning if missing
    # required_vocabs = [required_taxonomy_columns,required_columns_spatial_vocab,required_columns_other]

    # check for taxonomic vocabulary
    taxonomy_report = None
    #for vocab_list in required_vocabs:
    if any(map(lambda v: v in required_taxonomy_columns, list(dataframe.columns))):

        # check to see if we are missing any columns
        check_missing_fields = set(list(dataframe.columns)).issuperset(required_taxonomy_columns)
        
        # check for any missing required fields
        if not check_missing_fields:
            missing_columns = list(set(required_taxonomy_columns).difference(set(dataframe.columns)))
            taxonomy_report = None
        else:
            if "scientificName" in list(dataframe.columns):
                # is this vocabs_reports or is this a separate thing?
                taxonomy_report = create_taxonomy_report(
                    dataframe=dataframe
                )
            else:
                taxonomy_report = None

    # check for required DwCA terms
    # required fields according to https://support.ala.org.au/support/solutions/articles/6000261427-sharing-a-dataset-with-the-ala
    ### TODO: refactor below code and write function for this
    if any(map(lambda v: v in required_columns_spatial_vocab, list(dataframe.columns))):
        
        # check to see if we are missing any columns
        check_missing_fields = set(list(dataframe.columns)).issuperset(required_columns_spatial_vocab)
        
        # check for any missing required fields
        if not check_missing_fields:
            missing_columns = list(set(required_columns_spatial_vocab).difference(set(dataframe.columns)))
        else:
            valid_data = validate_required_fields(dataframe,required_columns_spatial_vocab)

    else:
        check_missing_fields = set(list(dataframe.columns)).issuperset(required_columns_other)
        if type(check_missing_fields) is not bool and len(check_missing_fields) > 0:
            missing_columns = list(set(required_columns_other).difference(set(dataframe.columns)))
            missing_columns.append("MAYBE: decimalLatitude")
            missing_columns.append("MAYBE: decimalLongitude")
        else:
            valid_data = validate_required_fields(dataframe,required_columns_other)        

    # check that a unique ID is present for occurrences
    any_present=False
    for entry in ["occurrenceID", "catalogNumber", "recordNumber"]:
        # validate_required_fields(dataframe, [entry])
        check_missing_fields = set(list(dataframe.columns)).issuperset([entry])
        if check_missing_fields:
            any_present=True
            break
    
    # let user know that not of these are present
    if not any_present:
        missing_columns.append("occurrenceID OR catalogNumber OR recordNumber")
        
    # if ids of occurrences are present and all DwCA terms present,
    # set this to True
    if len(missing_columns) == 0:
        all_required_columns_present = True

    # check date information supplied - create warning if missing
    # valid_temporal_count = validate_required_fields(dataframe, ['eventDate'])
    # valid_temporal_count = 0

    # validate coordinates - create warning if out of range
    coordinates_report = generate_coordinates_report(dataframe, warnings)

    # validate datetime column
    datetime_report = create_datetime_report(dataframe)

    # check basic compliance with vocabs - basisOfRecord, geodeticDatum, etc.
    vocabs_reports = [
        create_vocabulary_report(
            dataframe,
            "basisOfRecord",
            basis_of_record_vocabulary)
    ]
    if ["geodeticDatum"] in list(dataframe.columns):
        vocabs_reports.append(
            create_vocabulary_report(
            dataframe,
            "geodeticDatum",
            geodetic_datum_vocabulary)
        )

    return DFValidationReport(
        record_type="Occurrence",
        record_count=len(dataframe),
        record_error_count=int(record_error_count),
        errors=errors,
        warnings=warnings,
        all_required_columns_present=all_required_columns_present,
        missing_columns=missing_columns,
        column_counts=field_populated_counts(dataframe),
        records_with_temporal_count=0, #change this
        coordinates_report=coordinates_report,
        taxonomy_report = taxonomy_report,
        vocab_reports=vocabs_reports,
    )


def validate_event_dataframe(dataframe: DataFrame) -> DFValidationReport:
    """
    Validate a pandas DataFrame containing event data.
    :param dataframe: the data frame to validate
    :return:
    """

    errors = []
    warnings = []

    # check id field are fully populated
    record_error_count = check_id_fields(["eventID"], "", dataframe, errors)

    # check numeric fields have numeric values
    validate_numeric_fields(dataframe, warnings)

    # check date information supplied - create warning if missing
    valid_temporal_count = validate_required_fields(
        dataframe, ['eventDate', 'year', 'month', 'day'])

    # validate coordinates - create warning if out of range
    coordinates_report = generate_coordinates_report(dataframe, warnings)

    # check recordedBy, recordedByID - create warning if missing
    valid_recorded_by_count = validate_required_fields(
        dataframe, ['recordedBy', 'recordedByID'])

    vocabs_reports = [
        create_vocabulary_report(
            dataframe, "geodeticDatum", geodetic_datum_vocabulary)
    ]

    return DFValidationReport(
        record_type="Event",
        record_count=len(dataframe),
        record_error_count=int(record_error_count),
        errors=errors,
        warnings=warnings,
        coordinates_report=coordinates_report,
        records_with_taxonomy_count=0,
        records_with_temporal_count=int(valid_temporal_count),
        records_with_recorded_by_count=int(valid_recorded_by_count),
        column_counts=field_populated_counts(dataframe),
        vocab_reports=vocabs_reports
    )


def validate_required_fields(dataframe: DataFrame, required_fields) -> int:
    """
    Count the number of records with at least one of the required fields populated.

    AB Note:
        Shouldn't this be checking if all required fields have data entries for each occurrence?

    Parameters
    -----------
        dataframe : pandas DataFrame
            the dataframe you want to validate
        required_fields : list
            a list of fields required by the DwCA standard and/or the chosen submission atlas

    Returns
    --------
        Count of records with at least one of the required fields populated.
        AB note: 
            I believe this should check for ALL required fields, not just one.
    """
    # Check if all required fields are present in the DataFrame
    if not any(field in dataframe.columns for field in required_fields):
        return 0

    # check only fields that are reqired
    present_fields = filter(lambda x: x in dataframe.columns, required_fields)

    # get the number of rows containing non-null values
    required_fields_populated_count = dataframe[present_fields].count(axis=0)
    
    # Return count for each column
    return required_fields_populated_count


def generate_coordinates_report(
        dataframe: DataFrame,
        warnings: List[str]) -> CoordinatesReport:
    """
    Validate 'decimalLatitude' and 'decimalLongitude' columns in a pandas DataFrame.

    Parameters
    -----------
        dataframe: pandas DataFrame
            the dataframe you are looking to validate
        warnings: list
            a list of warnings 

    Returns
    ---------
        An object of type ``CoordinatesReport``
    """
    # Check if 'decimalLatitude' and 'decimalLongitude' columns exist
    if 'decimalLatitude' not in dataframe.columns or 'decimalLongitude' not in dataframe.columns:
        # logging.error(
        #     "Error: 'decimalLatitude' or 'decimalLongitude' columns not found.")
        return CoordinatesReport(False, 0, 0)

    # get a count of fields populated
    lat_column_non_empty_count = dataframe['decimalLatitude'].count()
    lon_column_non_empty_count = dataframe['decimalLongitude'].count()

    # get a count of fields populated with valid numeric values
    lat_column = pd.to_numeric(dataframe['decimalLatitude'], errors='coerce')
    lon_column = pd.to_numeric(dataframe['decimalLongitude'], errors='coerce')

    # check if all values are valid
    lat_valid_count = lat_column.astype(
        float).between(-90, 90, inclusive='both').sum()
    lon_valid_count = lon_column.astype(
        float).between(-180, 180, inclusive='both').sum()

    if lat_valid_count == lat_column_non_empty_count and lon_valid_count == lon_column_non_empty_count:
        logging.info("All supplied coordinate values are valid.")
        return CoordinatesReport(
            True,
            0, 0)

    logging.error("Error: Some values are not valid.")
    warnings.append("INVALID_OR_OUT_OF_RANGE_COORDINATES")
    return CoordinatesReport(
        True,
        int(lat_column_non_empty_count - lat_valid_count),
        int(lon_column_non_empty_count - lon_valid_count)
    )


def check_id_fields(
        id_fields: List[str],
        id_term: str,
        dataframe: DataFrame,
        errors: List[str]) -> int:
    """
    Check that the id fields [WHAT ARE THESE AMANDA] are populated for all rows and that the values are unique.
    If ...

    Parameters
    -----------
        id_fields : list
            the fields used to specify a unique identifier for the record (either or any of occurrenceID, catalogNumber, SOMETHING ELSE)
        id_term : str/list?
            the actual darwin core term used for the id field e.g. occurrenceID, catalogNumber
        dataframe: pandas.DataFrame
            the data frame to validate
        errors: list
            the list of errors to append to

    Returns
    --------
        [An object of class `pandas.DataFrame`???] records that are missing an id field
    """

    if not id_fields:
        return 0

    for field in id_fields:

        if id_term == field:
            id_field_series = dataframe['id']
        elif field in dataframe.columns:
            id_field_series = dataframe[field]
        else:
            errors.append("MISSING_ID_FIELD")
            logging.error(
                "The %s field is not present in the core file.", field)
            return len(dataframe)

        if id_field_series.notnull().all():
            logging.info("The occurrenceID field is populated for all rows.")

            if len(id_fields) == 1:
                if id_field_series.nunique() == dataframe.shape[0]:
                    logging.info(
                        "The %s has unique values for all rows.", field)
                else:
                    errors.append("DUPLICATE_ID_FIELD_VALUES")
                    logging.error(
                        "The %s field does not have unique values for all rows.", field)
                    return id_field_series.duplicated().sum()
        else:
            errors.append("MISSING_ID_FIELD_VALUES")
            logging.error("The %s field is not populated for all rows.", field)
            return id_field_series.isna().sum()

    return 0


def create_vocabulary_report(
        dataframe: DataFrame,
        field: str,
        controlled_vocabulary: List[str]) -> VocabularyReport:
    """
    Count the number of records with a case-insensitive value in the specified field matching a controlled vocabulary.

    Parameters
    -----------
        dataframe : ``pandas`` DataFrame
            dataframe to validate for DwC terms
        field : str
            the field/column in the DataFrame to check
        controlled_vocabulary : list or set
            a list of the controlled vocabulary (in this case DwC terms) to compare against

    Returns
    --------
        Count of records with a case-insensitive value in the specified field matching the controlled vocabulary.
    """

    # Check if the specified field is present in the DataFrame
    if field not in dataframe.columns:
        # logging.error("Error: Field '%s' not found in the DataFrame.", field)
        return VocabularyReport(field, False, 0, 0, [])

    # Convert both field values and controlled vocabulary to lowercase (or
    # uppercase)
    not_populated_count = dataframe[field].isna().sum()
    populated_values = dataframe[field].dropna()
    non_matching = []
    matching_records_count = 0

    if len(populated_values) > 0:
        field_values_lower = populated_values.str.lower()
        controlled_vocabulary_lower = set(
            value.lower() for value in controlled_vocabulary)

        # Count the number of records with a case-insensitive value in the
        # specified field matching the controlled vocabulary
        matching_records_count = field_values_lower.isin(
            controlled_vocabulary_lower).sum()

        # pylint: disable=broad-exception-caught
        try:
            x = dataframe.loc[~dataframe[field].str.lower().isin(controlled_vocabulary_lower)][field].to_numpy()
            non_matching = numpy.unique(x.astype(numpy.str_))[:10].tolist()
            if 'nan' in non_matching:
                non_matching.remove('nan')
        except Exception as e:
            logging.error("Error with getting non matching values %s", e, exc_info=True)
            non_matching = []

    # Print the count and return it
    logging.info(
        "Count of records with a case-insensitive value in '%s' "
        "matching the controlled vocabulary: %s", field, matching_records_count)
    return VocabularyReport(
        field=field,
        has_field=True,
        recognised_count=int(matching_records_count),
        unrecognised_count=int(len(dataframe) - (not_populated_count + matching_records_count)),
        non_matching_values=non_matching
    )


def validate_numeric_fields(dataframe: DataFrame, warnings: List[str]):
    """
    Check that the numeric fields have numeric values.

    Parameters
    -----------
        dataframe: `pandas` dataFrame 
            the data frame to validate
        warnings : list 
            the list of warnings to append to

    Returns
    --------
        a list of warnings pertaining to your numeric fields
    """
    numeric_fields = [
        'decimalLatitude',
        'decimalLongitude',
        'coordinateUncertaintyInMeters',
        'coordinatePrecision',
        'elevation',
        'depth',
        'minimumDepthInMeters',
        'maximumDepthInMeters',
        'minimumDistanceAboveSurfaceInMeters',
        'maximumDistanceAboveSurfaceInMeters',
        'individualCount',
        'organismQuantity',
        'organismSize',
        'sampleSizeValue',
        'temperatureInCelsius',
        'organismAge',
        'year',
        'month',
        'day',
        'startDayOfYear',
        'endDayOfYear']

    for field in numeric_fields:
        if field in dataframe.columns:

            numeric_test = pd.to_numeric(dataframe[field], errors='coerce')

            # Check if the values are either numeric or NaN (for empty strings)
            is_numeric_or_empty = numeric_test.apply(lambda x: pd.isna(x) or pd.api.types.is_numeric_dtype(
                x) or pd.api.types.is_float(x) or pd.api.types.is_integer(x))

            # Return True if all values are numeric or empty, False otherwise
            is_valid = is_numeric_or_empty.all()

            if not is_valid:
                logging.error(
                    "Non-numeric values found in field: %s", field)
                warnings.append(f"NON_NUMERIC_VALUES_IN_{field.upper()}")

    return warnings

def create_taxonomy_report(dataframe: DataFrame,
                           num_matches: int = 5,
                           include_synonyms: bool = True,
                           ) -> TaxonReport:
    """
    Check if the given taxon in a data frame are valid for chosen atlas backbone.

    Parameters
    ----------
        dataframe : `pandas` dataframe
            the data frame to validate
        num_matches : int
            the maximum number of possible matches to return when searching for matches in chosen atlas
        include_synonyms : logical
            an option to include any synonyms of the identified taxon in your search

    Returns
    -------
        An object of class `TaxonReport` that givs information on invalid and unrecognised taxa, as well as
        suggested names for taxon that don't match the taxonomic backbone you are checking.
    """
    ### TODO: add configuration for atlas later
    # check for scientificName, return None if it is not in the column names
    if "scientificName" not in list(dataframe.columns):
        return None
    
    # make a list of all scientific names in the dataframe
    scientific_names_list = list(set(dataframe["scientificName"]))

    # initialise has_invalid_taxa
    has_invalid_taxa=False
    
    # send list of scientific names to ALA to check their validity
    payload = [{"scientificName": name} for name in scientific_names_list]
    response = requests.request("POST","https://api.ala.org.au/namematching/api/searchAllByClassification",data=json.dumps(payload))
    response_json = response.json()
    terms = ["original name"] + ["proposed match(es)"] + ["rank of proposed match(es)"] + taxon_terms["Australia"]
    invalid_taxon_dict = {x: [] for x in terms}
    
    # loop over list of names and ensure we have gotten all the issues - might need to do single name search
    # to ensure we get everything
    for i,item in enumerate(scientific_names_list):
        item_index = next((index for (index, d) in enumerate(response_json) if "scientificName" in d and d["scientificName"] == item), None)
        # taxonomy["scientificName"][i] = item
        if item_index is None:
            # make this better
            has_invalid_taxa = True
            response_single = requests.get("https://api.ala.org.au/namematching/api/autocomplete?q={}&max={}&includeSynonyms={}".format("%20".join(item.split(" ")),num_matches,str(include_synonyms).lower()))
            response_json_single = response_single.json()
            if response_json_single:
                if response_json_single[0]['rank'] is not None:
                    invalid_taxon_dict["original name"].append(item)
                    invalid_taxon_dict["proposed match(es)"].append(response_json_single[0]['name'])
                    invalid_taxon_dict["rank of proposed match(es)"].append(response_json_single[0]['rank'])
                    for term in taxon_terms["Australia"]:
                        if term in response_json_single[0]['cl']:
                            invalid_taxon_dict[term].append(response_json_single[0]['cl'][term])
                        else:
                            invalid_taxon_dict[term].append(None)
                else:

                    # check for synonyms
                    for synonym in response_json_single[0]["synonymMatch"]:
                        if synonym['rank'] is not None:
                            invalid_taxon_dict["original name"].append(item)
                            invalid_taxon_dict["proposed match(es)"].append(synonym['name'])
                            invalid_taxon_dict["rank of proposed match(es)"].append(synonym['rank'])
                            for term in taxon_terms["Australia"]:
                                if term in synonym['cl']:
                                    invalid_taxon_dict[term].append(synonym['cl'][term])
                            else:
                                invalid_taxon_dict[term].append(None)
                        else:
                            print("synonym doesn't match")
            else:
                # try one last time to find a match
                response_search = requests.get("https://api.ala.org.au/namematching/api/search?q={}".format("%20".join(item.split(" "))))
                response_search_json = response_search.json()            
                if response_search_json['success']:
                    invalid_taxon_dict["original name"].append(item)
                    invalid_taxon_dict["proposed match(es)"].append(response_search_json['scientificName'])
                    invalid_taxon_dict["rank of proposed match(es)"].append(response_search_json['rank'])
                    for term in taxon_terms["Australia"]:
                        if term in response_search_json:
                            invalid_taxon_dict[term].append(response_search_json[term])
                        else:
                            invalid_taxon_dict[term].append(None)
                else:
                    print("last ditch search did not work")
                    print(response_search_json)
                    import sys
                    sys.exit()
    
    valid_taxon_count = 999
    if not has_invalid_taxa:
        # now 
        valid_data = validate_required_fields(dataframe,required_taxonomy_columns)
        for entry in valid_data.items():
            if entry[0] != "vernacularName":
                if entry[1] < dataframe.shape[0]:
                    if entry[1] < valid_taxon_count:
                        valid_taxon_count = entry[1]
        if dataframe.shape[0] < valid_taxon_count:
            valid_taxon_count = dataframe.shape[0]
    else:
        valid_taxon_count = 0

    # return report on taxon
    return TaxonReport(
        has_invalid_taxa = has_invalid_taxa,
        unrecognised_taxa = invalid_taxon_dict,
        valid_taxon_count = valid_taxon_count
    )

def create_datetime_report(dataframe):
    """
    Something here
    """

    # first, check for eventDate
    if 'eventDate' not in dataframe.columns:
        return {True,dataframe.shape[0]}
    
    event_dates = dataframe['eventDate']
    print(event_dates)
    print(event_dates[0])
    print(type(event_dates[0]))
    import sys
    sys.exit()