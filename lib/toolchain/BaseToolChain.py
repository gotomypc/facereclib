#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Manuel Guenther <Manuel.Guenther@idiap.ch>

import os
import numpy
import bob
import utils

class ProcessingToolChain:
  """This class includes functionalities for a default tool chain to produce verification scores"""
  
  def __init__(self, file_selector):
    """Initializes the tool chain object with the current file selector"""
    self.m_file_selector = file_selector
    
  def __save__(self, data, filename):
    utils.ensure_dir(os.path.dirname(filename))
    if hasattr(data, 'save'):
      # this is some class that supports saving itself
      data.save(bob.io.HDF5File(str(filename)))
    else:
      # this is most probably a numpy.ndarray that can be saved by bob.io.save
      bob.io.save(data, str(filename))
      
 
  def __check_file__(self, filename, force, expected_file_size = 1):
    """Checks if the file exists and has size greater or equal to expected_file_size.
    If the file is to small, or if the force option is set to true, the file is removed.
    This function returns true is the file is there, otherwise false"""
    if os.path.exists(filename):
      if force or os.path.getsize(filename) < expected_file_size:
        print "Removing old file '%s'." % filename
        os.remove(filename)
        return False
      else:
        return True
    return False
    
    
  def preprocess_images(self, preprocessor, indices=None, force=False):
    """Preprocesses the images with the given preprocessing tool"""
    # get the file lists      
    image_files = self.m_file_selector.original_image_list()
    # read eye files
    eye_files = self.m_file_selector.eye_position_list()
    preprocessed_image_files = self.m_file_selector.preprocessed_image_list()
    
    # iterate through the images and perform normalization
    keys = sorted(image_files.keys())
    if indices != None:
      keys = keys[indices[0]:indices[1]]
    for k in keys:
      image_file = image_files[k]
      preprocessed_image_file = preprocessed_image_files[k]
      eye_file = eye_files[k]

      if self.__check_file__(preprocessed_image_file, force):
        print "Preprocessed image '%s' already exists."  % preprocessed_image_file
      else:
        print "Generating preprocessed image '%s' from file '%s'." % (preprocessed_image_file, image_file)

        # read eyes position file
        annots = [int(j.strip()) for j in open(eye_file).read().split()]
        if self.m_file_selector.m_db_options.first_annot == 0: 
          eye_positions = annots[0:4]
        else: 
          eye_positions = annots[1:5]
          
        # call the image preprocessor
        utils.ensure_dir(os.path.dirname(preprocessed_image_file))
        preprocessed_image = preprocessor(image_file, eye_positions)
        bob.io.save(preprocessed_image, str(preprocessed_image_file))
  
  
  
  def train_extractor(self, extractor, force = False):
    """Trains the feature extractor, if it requires training"""
    if hasattr(extractor,'train'):
      extractor_file = self.m_file_selector.extractor_file()
      if self.__check_file__(extractor_file, force):
        print "Extractor '%s' already exists." % extractor_file
      else:
        # train model
        train_files = self.m_file_selector.training_image_list() 
        print "Training Extractor '%s' using %d training files: " %(extractor_file, len(train_files))
        extractor.train(train_files, extractor_file)

    
  
  def extract_features(self, extractor, indices = None, force=False):
    """Extracts the features using the given extractor"""
    if hasattr(extractor, 'load'):
      extractor.load(self.m_file_selector.extractor_file())
    image_files = self.m_file_selector.preprocessed_image_list()
    feature_files = self.m_file_selector.feature_list()

    # extract the features
    keys = sorted(image_files.keys())
    if indices != None:
      keys = keys[indices[0]:indices[1]]
    for k in keys:
      image_file = image_files[k]
      feature_file = feature_files[k]
      
      if self.__check_file__(feature_file, force):
        print "Feature file '%s' already exists."  % (feature_file)
      else:
        print "Computing feature file '%s' from sample '%s'." % (feature_file, image_file)
        # load image
        image = bob.io.load(str(image_file))
        # extract feature
        feature = extractor(image)
        # Save feature
        self.__save__(feature, str(feature_file))
    
      

  def train_projector(self, tool, force=False):
    """Train the feature extraction process with the preprocessed images of the world group"""
    if hasattr(tool,'train_projector'):
      projector_file = self.m_file_selector.projector_file()
      
      if self.__check_file__(projector_file, force):
        print "Projector '%s' already exists." % projector_file
      else:
        # train model
        train_files = self.m_file_selector.training_feature_list() 
        print "Training Projector '%s' using %d training files: " %(projector_file, len(train_files))
  
        # perform training
        tool.train_projector(train_files, str(projector_file))
 
    
  def project_features(self, tool, indices = None, force=False):
    """Extract the features for all files of the database"""
    # load the projector file
    if hasattr(tool, 'project'):
      if hasattr(tool, 'load_projector'):
        tool.load_projector(self.m_file_selector.projector_file())
      
      feature_files = self.m_file_selector.feature_list()
      projected_files = self.m_file_selector.projected_list()
      # extract the features
      keys = sorted(feature_files.keys())
      if indices != None:
        keys = keys[indices[0]:indices[1]]
      for k in keys:
        feature_file = feature_files[k]
        projected_file = projected_files[k]
        
        if self.__check_file__(projected_file, force):
          print "Projected file '%s' already exists."  % (projected_file)
        else:
          print "Projecting feature '%s' from sample '%s'." % (projected_file, feature_file)
          # load feature
          feature = bob.io.load(str(feature_file))
          # project feature
          projected = tool.project(feature)
          # write it
          utils.ensure_dir(os.path.dirname(projected_file))
          self.__save__(projected, projected_file)
  
    
  def __read_feature__(self, feature_file):
    """This function reads the model from file. Overload this function if your model is no numpy.ndarray."""
    if hasattr(self.m_tool, 'read_feature'):
      return self.m_tool.read_feature(feature_file)
    else:
      return bob.io.load(feature_file)
  
  def train_enroler(self, tool, force=False):
    """Traines the model enrolment stage using the projected features"""
    self.m_tool = tool
    if hasattr(tool, 'train_enroler'):
      enroler_file = self.m_file_selector.enroler_file()
      
      if self.__check_file__(enroler_file, force):
        print "Enroler '%s' already exists." % enroler_file
      else:
        if hasattr(tool, 'load_projector'):
          tool.load_projector(self.m_file_selector.projector_file())
        # training models
        train_files = self.m_file_selector.training_feature_list_by_models('projected')
  
        # perform training
        print "Training Enroler '%s' using %d training files: " %(enroler_file, len(train_files))
        tool.train_enroler(train_files, str(enroler_file))

    
  def enrol_models(self, tool, compute_zt_norm, indices = None, groups = ['dev', 'eval'], types = ['N','T'], force=False):
    """Enrol the models for 'dev' and 'eval' groups, for both models and T-Norm-models.
       This function by default used the projected features to compute the models.
       If you need unprojected features for the model, please define a variable with the name 
       use_unprojected_features_for_model_enrol"""
    
    self.m_tool = tool
    # read the projector file, if needed
    if hasattr(tool,'load_projector'):
      # read the feature extraction model
      tool.load_projector(self.m_file_selector.projector_file())
    if hasattr(tool, 'load_enroler'):
      # read the model enrolment file
      tool.load_enroler(self.m_file_selector.enroler_file())
      

    use_projected_features = hasattr(tool, 'project') and not hasattr(tool, 'use_unprojected_features_for_model_enrol')

    # Create Models
    if 'N' in types:
      for group in groups:
        model_ids = self.m_file_selector.model_ids(group)

        if indices != None: 
          model_ids = model_ids[indices[0]:indices[1]]

        for model_id in model_ids:
          # Path to the model
          model_file = self.m_file_selector.model_file(model_id, group)

          # Removes old file if required
          if self.__check_file__(model_file, force):
            print "Model %s already exists." % model_file
          else:
            enrol_files = self.m_file_selector.enrol_files(model_id, group, use_projected_features)
            
            # load all files into memory
            enrol_features = []
            for k in sorted(enrol_files.keys()):
              # processes one file
              feature = self.__read_feature__(str(enrol_files[k]))
              enrol_features.append(feature)
            
            print "Enroling model", model_file, "from", len(enrol_features), "features"
            model = tool.enrol(enrol_features)
            # save the model
            self.__save__(model, model_file)

    # T-Norm-Models
    if 'T' in types and compute_zt_norm:
      for group in groups:
        model_ids = self.m_file_selector.Tmodel_ids(group)

        if indices != None: 
          model_ids = model_ids[indices[0]:indices[1]]

        for model_id in model_ids:
          # Path to the model
          model_file = self.m_file_selector.Tmodel_file(model_id, group)

          # Removes old file if required
          if self.__check_file__(model_file, force):
            print "Tmodel %s already exists." % model_file
          else:
            enrol_files = self.m_file_selector.Tenrol_files(model_id, group, use_projected_features)

            # load all files into memory
            enrol_features = []
            for k in sorted(enrol_files.keys()):
              # processes one file
              
              feature = self.__read_feature__(str(enrol_files[k]))
              enrol_features.append(feature)
              
            print "Enroling Tmodel", model_file, "from", len(enrol_features), "features"
            model = tool.enrol(enrol_features)
            # save model
            self.__save__(model, model_file)


  def __read_model__(self, model_file):
    """This function reads the model from file. Overload this function if your model is no numpy.ndarray."""
    if hasattr(self.m_tool, 'read_model'):
      return self.m_tool.read_model(model_file)
    else:
      return bob.io.load(model_file)
    
  def __read_probe__(self, probe_file):
    """This function reads the probe from file. Overload this function if your probe is no numpy.ndarray."""
    if hasattr(self.m_tool, 'read_probe'):
      return self.m_tool.read_probe(probe_file)
    else:
      return bob.io.load(probe_file)

  def __scores__(self, model, probe_objects):
    """Compute simple scores for the given model"""
    scores = numpy.ndarray((1,len(probe_objects)), 'float64')

    # Loops over the probes
    i = 0
    for k in sorted(probe_objects.keys()):
      # read probe
      probe = self.__read_probe__(str(probe_objects[k][0]))
      # compute score
      scores[0,i] = self.m_tool.score(model, probe)
      i += 1
    # Returns the scores
    return scores
    
  def __scores_preloaded__(self, model, probes):
    """Compute simple scores for the given model"""
    scores = numpy.ndarray((1,len(probes)), 'float64')

    # Loops over the probes
    i = 0
    for k in sorted(probes.keys()):
      # take pre-loaded probe
      probe = probes[k]
      # compute score
      scores[0,i] = self.m_tool.score(model, probe)
      i += 1
    # Returns the scores
    return scores
    
    
  def __probe_split__(self, selected_probe_objects, probes):
    sel = 0
    res = {}
    # iterate over all probe files
    for k in (selected_probe_objects.keys()):
      # add probe
      res[k] = probes[k]

    # return the split database
    return res
    

  def __scores_A__(self, model_ids, group, compute_zt_norm, force, preload_probes):
    """Computes A scores"""
    # preload the probe files for a faster access (and fewer network load)
    if preload_probes:
      print "Preloading probe files"
      all_probe_objects = self.m_file_selector.probe_files(group, self.m_use_projected_dir)
      all_probes = {}
      # read all probe files into memory
      for k in sorted(all_probe_objects.keys()):
        all_probes[k] = self.__read_probe__(str(all_probe_objects[k][0]))
      print "Computing A matrix"

    # Computes the raw scores for each model
    for model_id in model_ids:
      # test if the file is already there
      score_file = self.m_file_selector.A_file(model_id, group) if compute_zt_norm else self.m_file_selector.no_norm_file(model_id, group)
      if self.__check_file__(score_file, force):
        print "Score file '%s' already exists." % (score_file)
      else:
        # get the probe split
        probe_objects = self.m_file_selector.probe_files_for_model(model_id,group, self.m_use_projected_dir)
        model = self.__read_model__(self.m_file_selector.model_file(model_id, group))
        if preload_probes:
          # select the probe files for this model from all probes
          current_probes = self.__probe_split__(probe_objects, all_probes)
          # compute A matrix
          A = self.__scores_preloaded__(model, current_probes)
        else:
          A = self.__scores__(model, probe_objects)
  
        if compute_zt_norm:
          # write A matrix only when you want to compute zt norm afterwards
          bob.io.save(A, self.m_file_selector.A_file(model_id, group))
  
        # Saves to text file
        scores_list = utils.convertScoreToList(numpy.reshape(A,A.size), probe_objects)
        f_nonorm = open(self.m_file_selector.no_norm_file(model_id, group), 'w')
        for x in scores_list:
          f_nonorm.write(str(x[2]) + " " + str(x[0]) + " " + str(x[3]) + " " + str(x[4]) + "\n")
        f_nonorm.close()
    
  def __scores_B__(self, model_ids, group, force, preload_probes):
    """Computes B scores"""
    # probe files:
    Zprobe_objects = self.m_file_selector.Zprobe_files(group, self.m_use_projected_dir)
    # preload the probe files for a faster access (and fewer network load)
    if preload_probes:
      print "Preloading probe files"
      Zprobes = {}
      # read all probe files into memory
      for k in sorted(Zprobe_objects.keys()):
        Zprobes[k] = self.__read_probe__(str(Zprobe_objects[k][0]))
      print "Computing B matrix"

    # Loads the models
    for model_id in model_ids:
      # test if the file is already there
      score_file = self.m_file_selector.B_file(model_id, group)
      if self.__check_file__(score_file, force):
        print "Score file '%s' already exists." % (score_file)
      else:
        model = self.__read_model__(self.m_file_selector.model_file(model_id, group))
        if preload_probes:
          B = self.__scores_preloaded__(model, Zprobes)
        else:
          B = self.__scores__(model, Zprobe_objects)
        bob.io.save(B, score_file)
    
  def __scores_C__(self, Tmodel_ids, group, force, preload_probes):
    """Computed C scores"""
    # probe files:
    probe_objects = self.m_file_selector.probe_files(group, self.m_use_projected_dir)

    # preload the probe files for a faster access (and fewer network load)
    if preload_probes:
      print "Preloading probe files"
      probes = {}
      # read all probe files into memory
      for k in sorted(probe_objects.keys()):
        probes[k] = self.__read_probe__(str(probe_objects[k][0]))
      print "Computing C matrix"

    # Computes the raw scores for the T-Norm model
    for Tmodel_id in Tmodel_ids:
      # test if the file is already there
      score_file = self.m_file_selector.C_file(Tmodel_id, group)
      if self.__check_file__(score_file, force):
        print "Score file '%s' already exists." % (score_file)
      else:
        Tmodel = self.__read_model__(self.m_file_selector.Tmodel_file(Tmodel_id, group))
        if preload_probes:
          C = self.__scores_preloaded__(Tmodel, probes)
        else:
          C = self.__scores__(Tmodel, probe_objects)
        bob.io.save(C, score_file)
      
  def __scores_D__(self, Tmodel_ids, group, force, preload_probes):
    # probe files:
    Zprobe_objects = self.m_file_selector.Zprobe_files(group, self.m_use_projected_dir)
    # preload the probe files for a faster access (and fewer network load)
    if preload_probes:
      print "Preloading probe files"
      Zprobes = {}
      # read all probe files into memory
      for k in sorted(Zprobe_objects.keys()):
        Zprobes[k] = self.__read_probe__(str(Zprobe_objects[k][0]))
      print "Computing D matrix"

    # Gets the Z-Norm impostor samples
    Zprobe_ids = []
    for k in Zprobe_objects.keys():
      Zprobe_ids.append(Zprobe_objects[k][3])

    # Loads the T-Norm models
    for Tmodel_id in Tmodel_ids:
      # test if the file is already there
      score_file = self.m_file_selector.D_same_value_file(Tmodel_id, group)
      if self.__check_file__(score_file, force):
        print "Score file '%s' already exists." % (score_file)
      else:
        Tmodel = self.__read_model__(self.m_file_selector.Tmodel_file(Tmodel_id, group))
        if preload_probes:
          D = self.__scores_preloaded__(Tmodel, Zprobes)
        else:
          D = self.__scores__(Tmodel, Zprobe_objects)
        bob.io.save(D, self.m_file_selector.D_file(Tmodel_id, group))
  
        Tmodel_ids = [self.m_file_selector.m_config.db.getClientIdFromModelId(Tmodel_id)]
        D_sameValue_tm = bob.machine.ztnormSameValue(Tmodel_ids, Zprobe_ids)
        bob.io.save(D_sameValue_tm, score_file)


  def compute_scores(self, tool, compute_zt_norm, force = False, indices = None, groups = ['dev', 'eval'], types = ['A', 'B', 'C', 'D'], preload_probes = False):
    """Computes the scores for 'dev' and 'eval' groups"""
    # save tool for internal use
    self.m_tool = tool
    self.m_use_projected_dir = hasattr(tool, 'project')
    
    # load the projector, if needed
    if hasattr(tool,'load_projector'):
      tool.load_projector(self.m_file_selector.projector_file())
    if hasattr(tool,'load_enroler'):
      tool.load_enroler(self.m_file_selector.enroler_file())

    for group in groups:
      print "----- computing scores for group '%s' -----" % group
      # get model ids
      model_ids = self.m_file_selector.model_ids(group)
      if compute_zt_norm:
        Tmodel_ids = self.m_file_selector.Tmodel_ids(group)

      # compute A scores
      if 'A' in types:
        if indices != None: 
          model_ids_short = model_ids[indices[0]:indices[1]]
        else:
          model_ids_short = model_ids
        print "computing A scores"
        self.__scores_A__(model_ids_short, group, compute_zt_norm, force, preload_probes)
      
      if compute_zt_norm:
        # compute B scores
        if 'B' in types:
          if indices != None: 
            model_ids_short = model_ids[indices[0]:indices[1]]
          else:
            model_ids_short = model_ids
          print "computing B scores"
          self.__scores_B__(model_ids_short, group, force, preload_probes)
        
        # compute C scores
        if 'C' in types:
          if indices != None: 
            Tmodel_ids_short = Tmodel_ids[indices[0]:indices[1]]
          else:
            Tmodel_ids_short = Tmodel_ids
          print "computing C scores"
          self.__scores_C__(Tmodel_ids_short, group, force, preload_probes)
        
        # compute D scores
        if 'D' in types:
          if indices != None: 
            Tmodel_ids_short = Tmodel_ids[indices[0]:indices[1]]
          else:
            Tmodel_ids_short = Tmodel_ids
          print "computing D scores"
          self.__scores_D__(Tmodel_ids_short, group, force, preload_probes)
      
      

  def __scores_C_normalize__(self, model_ids, Tmodel_ids, group):
    """Compute normalized probe scores using Tmodel scores"""
    # read all Tmodel scores
    C_for_all = None
    for Tmodel_id in Tmodel_ids:
      tmp = bob.io.load(self.m_file_selector.C_file(Tmodel_id, group))
      if C_for_all == None:
        C_for_all = tmp
      else:
        C_for_all = numpy.vstack((C_for_all, tmp))
    # iterate over all models and genarate C matrices for that specific model
    probe_objects = self.m_file_selector.probe_files(group, False)
    for model_id in model_ids:
      # select the correct probe files for the current model
      model_probes = self.m_file_selector.probe_files_for_model(model_id, group, False)
      probes_used = utils.probes_used_generate_vector(probe_objects, model_probes)
      C_for_model = utils.probes_used_extract_scores(C_for_all, probes_used)
      # Save C matrix to file
      bob.io.save(C_for_model, self.m_file_selector.C_file_for_model(model_id, group))

  def __scores_D_normalize__(self, Tmodel_ids, group):
    # initailize D and D_same_value matrices
    D_for_all = None
    D_same_value = None
    for Tmodel_id in Tmodel_ids:
      tmp = bob.io.load(self.m_file_selector.D_file(Tmodel_id, group))
      tmp2 = bob.io.load(self.m_file_selector.D_same_value_file(Tmodel_id, group))
      if D_for_all == None and D_same_value == None:
        D_for_all = tmp
        D_same_value = tmp2
      else:
        D_for_all = numpy.vstack((D_for_all, tmp))
        D_same_value = numpy.vstack((D_same_value, tmp2))

    # Saves to files
    bob.io.save(D_for_all, self.m_file_selector.D_matrix_file(group))
    bob.io.save(D_same_value, self.m_file_selector.D_same_value_matrix_file(group))
  

  def zt_norm(self, groups=['dev', 'eval']):
    """Computes ZT-Norm using the previously generated files"""
    for group in groups:
      # list of models
      model_ids = self.m_file_selector.model_ids(group)
      Tmodel_ids = self.m_file_selector.Tmodel_ids(group)

      # first, normalize C and D scores
      self.__scores_C_normalize__(model_ids, Tmodel_ids, group)
      # and normalize it
      self.__scores_D_normalize__(Tmodel_ids, group)


      # load D matrices only once
      D = bob.io.load(self.m_file_selector.D_matrix_file(group))
      D_sameValue = bob.io.load(self.m_file_selector.D_same_value_matrix_file(group)).astype(bool)
      # Loops over the model ids
      for model_id in model_ids:
        # Loads probe files to get information about the type of access
        probe_objects = self.m_file_selector.probe_files_for_model(model_id, group, False)

        # Loads A, B, C, D and D_sameValue matrices
        A = bob.io.load(self.m_file_selector.A_file(model_id, group))
        B = bob.io.load(self.m_file_selector.B_file(model_id, group))
        C = bob.io.load(self.m_file_selector.C_file_for_model(model_id, group))
        
        # compute zt scores
        ztscores_m = bob.machine.ztnorm(A, B, C, D, D_sameValue)

        # Saves to text file
        ztscores_list = utils.convertScoreToList(numpy.reshape(ztscores_m, ztscores_m.size), probe_objects)
        sc_ztnorm_filename = self.m_file_selector.zt_norm_file(model_id, group)
        f_ztnorm = open(sc_ztnorm_filename, 'w')
        for x in ztscores_list:
          f_ztnorm.write(str(x[2]) + " " + str(x[0]) + " " + str(x[3]) + " " + str(x[4]) + "\n")
        f_ztnorm.close()
    
    
  def concatenate(self, compute_zt_norm, groups=['dev','eval']):
    """Concatenates all results into one score file"""
    for group in groups:
      # (sorted) list of models
      model_ids = self.m_file_selector.model_ids(group)

      f = open(self.m_file_selector.no_norm_result_file(group), 'w')
      # Concatenates the scores
      for model_id in model_ids:
        res_file = open(self.m_file_selector.no_norm_file(model_id, group), 'r')
        f.write(res_file.read())
      f.close()

      if compute_zt_norm:
        f = open(self.m_file_selector.zt_norm_result_file(group), 'w')
        # Concatenates the scores
        for model_id in model_ids:
          res_file = open(self.m_file_selector.zt_norm_file(model_id, group), 'r')
          f.write(res_file.read())
        f.close()
    
    
