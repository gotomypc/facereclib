#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Roy Wallace <Roy.Wallace@idiap.ch>

import bob
import numpy
import types
from . import UBMGMMVideoTool, ISVTool
from .. import utils

# Parent classes:
# - Warning: This class uses multiple inheritance! (Note: Python's resolution rule is: depth-first, left-to-right)
# - ISVTool extends UBMGMMTool by providing some additional methods for training the session variability subspace, etc.
# - UBMGMMVideoTool extends UBMGMMTool to support UBM training/enrolment/testing with VideoFrameContainers
#
# Here we extend the parent classes by overriding methods:
# -- read_feature --> overridden (use UBMGMMVideoTool's, to read a VideoFrameContainer)
# -- train_projector --> overridden (use UBMGMMVideoTool's)
# -- train_enroler --> overridden (based on ISVTool's, but projects only selected frames)
# -- project --> overridden (use UBMGMMVideoTool's)
# -- enrol --> overridden (based on ISVTool, but first projects only selected frames)
# -- read_model --> inherited from ISVTool (because it's inherited first)
# -- read_probe --> inherited from ISVTool (because it's inherited first)
# -- score --> inherited from ISVTool (because it's inherited first)

class ISVVideoTool (ISVTool, UBMGMMVideoTool):
  """Tool chain for video-to-video face recognition using inter-session variability modelling (ISV)."""
  
  def __init__(self, setup):
    ISVTool.__init__(self, setup)
    self.use_unprojected_features_for_model_enrol = True

  # Overrides ISVTool.train_enroler
  def train_enroler(self, train_files, enroler_file):
    print "-> ISVVideoTool.train_enroler"
    ########## (same as ISVTool.train_enroler)
    # create a JFABasemachine with the UBM from the base class
    self.m_jfabase = bob.machine.JFABaseMachine(self.m_ubm, self.m_config.ru)
    self.m_jfabase.ubm = self.m_ubm

    ########## calculate GMM stats from VideoFrameContainers, using frame_selector_for_train_enroler
    gmm_stats = [] 
    for k in sorted(train_files.keys()): # loop over clients
      gmm_stats_client = []
      for j in sorted(train_files[k].keys()): # loop over videos of client k
        frame_container = utils.VideoFrameContainer(str(train_files[k][j]))
        this_gmm_stats = UBMGMMVideoTool.project(self,frame_container,self.m_config.frame_selector_for_train_enroler)
        gmm_stats_client.append(this_gmm_stats)
      print "---> got " + str(len(gmm_stats_client)) + " gmm_stats for client ID " + str(k)
      gmm_stats.append(gmm_stats_client)
    print "--> got gmm_stats for " + str(len(gmm_stats)) + " clients"

    ########## (same as ISVTool.train_enroler)
    t = bob.trainer.JFABaseTrainer(self.m_jfabase)
    t.train_isv(gmm_stats, self.m_config.n_iter_train, self.m_config.relevance_factor)

    # Save the JFA base AND the UBM into the same file
    self.m_jfabase.save(bob.io.HDF5File(enroler_file, "w"))

  def enrol(self, frame_containers):
    print "-> ISVVideoTool.enrol"
    enrol_features = []
    for frame_container in frame_containers:
      this_enrol_features = UBMGMMVideoTool.project(self,frame_container,self.m_config.frame_selector_for_enrol)
      enrol_features.append(this_enrol_features)
    print "--> got " + str(len(enrol_features)) + " enrol_features"

    ########## (same as ISVTool.enrol)
    self.m_trainer.enrol(enrol_features, self.m_config.n_iter_enrol)
    return self.m_machine

  def read_feature(self, feature_file):
    return UBMGMMVideoTool.read_feature(self,str(feature_file))

  def project(self, frame_container):
    """Computes GMM statistics against a UBM, given an input VideoFrameContainer"""
    return UBMGMMVideoTool.project(self,frame_container)

  def train_projector(self, train_files, projector_file):
    """Computes the Universal Background Model from the training ("world") data"""
    return UBMGMMVideoTool.train_projector(self,train_files, projector_file)
