"""Failure-only evidence must be frozen before owned handles close."""
def capture_images(proc,reader):
 try:return reader(proc)
 except BaseException as error:return [{'metadataCaptureFailureClass':type(error).__name__,'complete':False,'normalCompletionQualified':False}]

def freeze_failure(proc,reader,sampler,root_code=None,preclose_images=None):
 failures=[];closed=bool(getattr(proc,'closed',False));proof=getattr(proc,'teardown',None);images=[]
 if proc is None:return {'teardownFailures':[],'teardownDiagnostic':{'treeState':'NO_PROCESS_STARTED','processTreeExitIndependentlyVerified':False},'ownedFailureImages':[],'knownParentExitObserved':True,'knownParentExitCode':None,'phaseProcessId':None}
 if preclose_images is not None:images=preclose_images
 elif closed:images=[{'metadataUnavailableClosedHandles':True,'complete':False,'normalCompletionQualified':False}]
 else:images=capture_images(proc,reader)
 if not closed and proof is None:
  try:proc.finish(terminate=True,sampler=sampler)
  except BaseException as error:failures.append(type(error).__name__)
 proof=getattr(proc,'teardown',None) or {'treeState':'UNKNOWN_OWNED_JOB_STATE','processTreeExitIndependentlyVerified':False}
 if root_code is None and not closed:
  try:root_code=proc.poll()
  except BaseException as error:failures.append('PARENT_EXIT_'+type(error).__name__)
 failures.extend(getattr(proc,'cleanup_errors',[]));pid=getattr(proc,'initial',{}).get('pid')
 # Freeze every API-dependent field before close. No closed-handle retry.
 result={'teardownFailures':failures,'teardownDiagnostic':proof,'ownedFailureImages':images,'knownParentExitObserved':root_code is not None,'knownParentExitCode':root_code,'phaseProcessId':pid}
 if not closed:
  try:proc.close()
  except BaseException as error:failures.append('CLOSE_'+type(error).__name__)
 return result
