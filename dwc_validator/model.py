"""
A module to represent the validation report for a Darwin Core Archive.
"""
from typing import List, Union


# pylint: disable=too-few-public-methods
class CoordinatesReport:
    """
    A class to represent a validation report for a Darwin Core Archive.
    """

    def __init__(self,
                 has_coordinates_fields: bool,  # has a decimalLatitude & decimalLongitude field
                 invalid_decimal_latitude_count: int,  # rows with invalid decimalLatitude
                 invalid_decimal_longitude_count: int  # rows with invalid decimalLongitude
                 ):
        self.has_coordinates_fields = has_coordinates_fields
        self.invalid_decimal_latitude_count = invalid_decimal_latitude_count
        self.invalid_decimal_longitude_count = invalid_decimal_longitude_count


# pylint: disable=too-few-public-methods
class VocabularyReport:
    """
    A class to represent a validation report for a Darwin Core Archive.
    """

    # pylint: disable=too-many-arguments)
    def __init__(self,
                 field: str,
                 has_field: bool,  # has the required field in the dataframe
                 recognised_count: int,  # rows with valid values
                 unrecognised_count: int,  # rows with invalid values
                 non_matching_values: List[str] = None  # list of non-matching values
                 ):
        self.field = field
        self.has_field = has_field
        self.recognised_count = recognised_count
        self.unrecognised_count = unrecognised_count
        self.non_matching_values = non_matching_values

class TaxonReport:
    """
    A class to represent a validation report for taxon names in a DwCA.
    """

    def __init__(self,
                 has_invalid_taxa: bool = False,
                 unrecognised_taxa: list = [],
                 suggested_names: dict = {}
                 ):
        self.has_invalid_taxa = has_invalid_taxa
        self.unrecognised_taxa = unrecognised_taxa
        self.suggested_names = suggested_names

# pylint: disable=too-few-public-methods,too-many-instance-attributes)
class DFValidationReport:
    """
    A class to represent a validation report for a pandas DataFrame.
    """

    # pylint: disable=too-many-arguments
    def __init__(self,
                 record_type: str,
                 record_count: int,
                 errors: [],
                 warnings: [],
                 column_counts: [],
                 record_error_count: int,
                 coordinates_report: Union[CoordinatesReport, None],
                 records_with_taxonomy_count: int,
                 taxonomy_report: TaxonReport,
                 records_with_temporal_count: int,
                 records_with_recorded_by_count: int,
                 vocab_reports: List[VocabularyReport] = None,
                 all_required_columns_present: bool = False,
                 missing_columns: list = [],
                 ):
        self.record_type = record_type
        self.record_count = record_count
        self.errors = errors
        self.warnings = warnings
        self.coordinates_report = coordinates_report
        self.column_counts = column_counts
        self.record_error_count = record_error_count
        self.records_with_taxonomy_count = records_with_taxonomy_count
        self.taxonomy_report = taxonomy_report
        self.records_with_temporal_count = records_with_temporal_count
        self.records_with_recorded_by_count = records_with_recorded_by_count
        self.vocab_reports = vocab_reports
        self.all_required_columns_present = all_required_columns_present
        self.missing_columns = missing_columns


# pylint: disable=too-few-public-methods
class DwCAValidationReport:
    """
    A class to represent a validation report for a Darwin Core Archive.
    """

    # pylint: disable=too-many-arguments
    def __init__(self,
                 valid: bool,
                 core_type: str,
                 dataset_type: str,
                 core_validation_report: DFValidationReport,
                 extension_validation_reports: List[DFValidationReport],
                 breakdowns: []):
        self.valid = valid
        self.core_type = core_type  # URI of the core type
        self.dataset_type = dataset_type  # "Occurrence" or "Event"
        self.core = core_validation_report  # DFValidationReport of the core dataframe
        # List of DFValidationReport of the extension dataframes
        self.extensions = extension_validation_reports
        # Consolidated list of breakdowns of the dataframe(s)
        self.breakdowns = breakdowns
