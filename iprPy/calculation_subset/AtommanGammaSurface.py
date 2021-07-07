# Standard Python libraries
from pathlib import Path

# http://www.numpy.org/
import numpy as np

# https://github.com/usnistgov/DataModelDict
from DataModelDict import DataModelDict as DM

# https://github.com/usnistgov/atomman
import atomman as am
import atomman.unitconvert as uc

from . import CalculationSubset
from ..tools import dict_insert, aslist
from ..input import termtodict, dicttoterm, value, boolean

class AtommanGammaSurface(CalculationSubset):
    """Handles calculation terms for loading gamma surface results using atomman"""
    
############################# Core properties #################################
     
    def __init__(self, parent, prefix=''):
        """
        Initializes a calculation record subset object.

        Parameters
        ----------
        parent : iprPy.calculation.Calculation
            The parent calculation object that the subset object is part of.
            This allows for the subset methods to access parameters set to the
            calculation itself or other subsets.
        prefix : str, optional
            An optional prefix to add to metadata field names to allow for
            differentiating between multiple subsets of the same style within
            a single record
        """
        super().__init__(parent, prefix=prefix)

        self.gammasurface_file = None
        self.__gammasurface_content = None
        self.__gamma = None    
        self.__calc_key = None

############################## Class attributes ################################
    
    @property
    def gammasurface_file(self):
        return self.__gammasurface_file

    @gammasurface_file.setter
    def gammasurface_file(self, value):
        if value is None:
            self.__gammasurface_file = None
        else:
            self.__gammasurface_file = Path(value)

    @property
    def gammasurface_content(self):
        return self.__gammasurface_content

    @property
    def gamma(self):
        if self.__gamma is None:
            return None
        elif not isinstance(self.__gamma, am.defect.GammaSurface):
            self.__gamma = am.defect.GammaSurface(model=self.__gamma)
        return self.__gamma

    @property
    def calc_key(self):
        return self.__calc_key

    def set_values(self, **kwargs):
        pass

####################### Parameter file interactions ###########################

    @property
    def templateheader(self):
        """str : The default header to use in the template file for the subset"""
        return '# Gamma surface parameters'

    @property
    def templatekeys(self):
        """
        list : The input keys (without prefix) that appear in the input file.
        """
        return [
            'gammasurface_file',
        ]
    
    @property
    def preparekeys(self):
        """
        list : The input keys (without prefix) used when preparing a calculation.
        Typically, this is templatekeys plus *_content keys so prepare can access
        content before it exists in the calc folders being prepared.
        """
        return self.templatekeys + [
            'gammasurface_content',
        ]

    @property
    def interpretkeys(self):
        """
        list : The input keys (without prefix) accessed when interpreting the 
        calculation input file.  Typically, this is preparekeys plus any extra
        keys used or generated when processing the inputs.
        """
        return self.preparekeys + [
            'gamma',
        ]

    def load_parameters(self, input_dict):
        """
        Interprets calculation parameters.
        
        Parameters
        ----------
        input_dict : dict
            Dictionary containing input parameter key-value pairs.
        """
        # Set default keynames
        keymap = self.keymap
        
        # Extract input values and assign default values
        self.gammasurface_file = input_dict.get(keymap['gammasurface_file'], None)
        self.__gammasurface_content = input_dict.get(keymap['gammasurface_content'], None)
        
        # Replace defect model with defect content if given
        gamma_file = self.gammasurface_file
        if self.gammasurface_content is not None:
            gamma_file = self.gammasurface_content
        
        # If defect model is given
        if gamma_file is not None:
            g_model = DM(gamma_file)
            self.__gamma = g_model
            self.__calc_key = g_model.finds('key')[0]
        else:
            raise ValueError('gammasurface_file is required')

########################### Data model interactions ###########################

    @property
    def modelroot(self):
        baseroot = 'stacking-fault-map'
        return f'{self.modelprefix}{baseroot}'

    def load_model(self, model):
        """Loads subset attributes from an existing model."""
        g_model = DM([('stacking-fault-map', model.find(self.modelroot) )])
        self.__gamma = am.defect.GammaSurface(model=g_model)
        self.__calc_key = g_model['stacking-fault-map']['calc_key']

    def build_model(self, model, **kwargs):
        """
        Converts the structured content to a simpler dictionary.
        
        Parameters
        ----------
        record_model : DataModelDict.DataModelDict
            The record content (after root element) to add content to.
        input_dict : dict
            Dictionary of all input parameter terms.
        results_dict : dict, optional
            Dictionary containing any results produced by the calculation.
        """
        # Save info on system file loaded
        g_model = self.gamma.model(length_unit=self.parent.units.length_unit)
        model[self.modelroot] = g_model['stacking-fault-map']
        model[self.modelroot]['calc_key'] = self.calc_key
        
    def metadata(self, meta):
        """
        Converts the structured content to a simpler dictionary.
        
        Parameters
        ----------
        meta : dict
            The dictionary to add the subset content to
        """
        meta[f'{self.prefix}gamma'] = self.gamma
        meta[f'{self.prefix}gammasurface_calc_key'] = self.calc_key


########################### Calculation interactions ##########################

    def calc_inputs(self, input_dict):

        input_dict['gamma'] = self.gamma