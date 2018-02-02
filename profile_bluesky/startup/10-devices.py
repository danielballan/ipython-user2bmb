print(__file__)


"""Set up default complex devices"""


import time
from ophyd import Component, Device, DeviceStatus
from ophyd import EpicsMotor, EpicsScaler
from ophyd import EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV
from ophyd import PVPositioner, PVPositionerPC
from ophyd import AreaDetector, PcoDetectorCam
from ophyd import SingleTrigger, ImagePlugin, HDF5Plugin
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite
from APS_BlueSky_tools.devices import userCalcsDevice


class EpicsMotorWithDial(EpicsMotor):
    """
    add motor record's dial coordinates to EpicsMotor
    
    USAGE::
    
        m1 = EpicsMotorWithDial('xxx:m1', name='m1')
    
    """
    dial = Component(EpicsSignal, ".DRBV", write_pv=".DVAL")


class EpicsMotorWithServo(EpicsMotor):
    """extend basic motor support to enable/disable the servo loop controls"""
    
    # values: "Enable" or "Disable"
    servo = Component(EpicsSignal, ".CNEN", string=True)


class Mirror1_A(Device):
    """
    Mirror 1 in the 2BM-A station
    
    A_mirror1 = Mirror1_A("2bma:M1", name="A_mirror1")
    A_mirror1.angle.put(Mirr_Ang)
    A_mirror1.average.put(Mirr_YAvg)
    """
    angle = Component(EpicsSignal, "angl")
    average = Component(EpicsSignal, "avg")


class AB_Shutter(Device):
    """
    A or B station shutter (PSS item)
    
    USAGE::

        A_shutter = AB_Shutter("2bma:A_shutter", name="A_shutter")
        A_shutter.open()
        A_shutter.close()

        B_shutter = AB_Shutter("2bma:B_shutter", name="B_shutter")
        B_shutter.close()

    """
    pss_open = Component(EpicsSignal, ":open")
    pss_close = Component(EpicsSignal, ":close")
    
    # TODO: how to know if is open or closed?  Need PV(s)

    def __init__(*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay = 1.0  # a hack because the shutter won�t say when it is done
    
    def open(self):
        """tells PSS to open the shutter"""
        self.pss_open.put(1)
    
    def close(self):
        """tells PSS to close the shutter"""
        self.pss_close.put(1)

    def set(self, value):       # interface for BlueSky plans
        """value is either open or close"""
        status = DeviceStatus(self)
        def run():
            if value == "open":
                self.open()
            elif value == "close":
                self.close()
            else:
                msg = "value should be either open or close."
                msg + " received " + str(value)
                raise ValueError(msg)
            yield from sleep(self.delay)
            status._finished(success=True)
        
        thread = threading.Thread(target=run)
        # TODO: look at Positioner code for being conservative about how many threads to create
        thread.start()      
        return status


class Motor_Shutter(Device):
    """
    a shutter, implemented with a motor
    
    USAGE::

        tomo_shutter = Motor_Shutter("2bma:m23", name="tomo_shutter")
        tomo_shutter.open()
        tomo_shutter.close()

    """
    motor = Component(EpicsMotor, "")
    closed_position = 1.0
    open_position = 0.0
    _tolerance = 0.01
    
    def isopen(self):
        return abs(self.motor.position - self.open_position) <= self._tolerance
    
    def isclosed(self):
        return abs(self.motor.position - self.closed_position) <= self._tolerance
    
    def open(self):
        """move motor to BEAM NOT BLOCKED position"""
        self.motor.move(self.open_position)
    
    def close(self):
        """move motor to BEAM BLOCKED position"""
        self.motor.move(self.closed_position)

    def set(self, value):       # interface for BlueSky plans
        """value is either open or close"""
        status = DeviceStatus(self)
        def run():
            if value == "open":
                yield from mv(self.motor, self.open_position)
            elif value == "close":
                yield from mv(self.motor, self.close_position)
            else:
                msg = "value should be either open or close."
                msg + " received " + str(value)
                raise ValueError(msg)
            status._finished(success=True)
        
        thread = threading.Thread(target=run)
        thread.start()      
        return status


class PSO_Device(Device):
    """PSO means ..."""
    # TODO: this might fit the ophyd "Flyer" API
    slew_speed = Component(EpicsSignal, "slewSpeed.VAL")
    scan_control = Component(EpicsSignal, "scanControl.VAL", string=True)
    start_pos = Component(EpicsSignal, "startPos.VAL")
    end_pos = Component(EpicsSignal, "endPos.VAL")
    scan_delta = Component(EpicsSignal, "scanDelta.VAL")
    pso_taxi = Component(EpicsSignal, "taxi.VAL", put_complete=True)
    pso_fly = Component(EpicsSignal, "fly.VAL", put_complete=True)
    
    def taxi(self):
        self.pso_taxi.put("Taxi")
    
    def fly(self):
        self.pso_fly.put("Fly")

    def set(self, value):       # interface for BlueSky plans
        """value is either Taxi or Fly"""
        status = DeviceStatus(self)
        def run():
            if value == "Taxi":
                self.taxi()
            elif value == "Fly":
                self.fly()
            else:
                msg = "value should be either Taxi or Fly."
                msg + " received " + str(value)
                raise ValueError(msg)
            yield from sleep(self.delay)
            status._finished(success=True)
        
        thread = threading.Thread(target=run)
        # TODO: look at Positioner code for being conservative about how many threads to create
        thread.start()      
        return status


class MyPcoCam(PcoDetectorCam):
    """PCO Dimax detector"""
    array_callbacks = Component(EpicsSignal, "ArrayCallbacks")
    pco_cancel_dump = Component(EpicsSignal, "pco_cancel_dump")
    pco_live_view = Component(EpicsSignal, "pco_live_view")
    pco_trigger_mode = Component(EpicsSignal, "pco_trigger_mode")
    pco_edge_fastscan = Component(EpicsSignal, "pco_edge_fastscan")
    pco_is_frame_rate_mode = Component(EpicsSignal, "pco_is_frame_rate_mode")
    pco_imgs2dump = Component(EpicsSignalWithRBV, "pco_imgs2dump")
    pco_dump_counter = Component(EpicsSignal, "pco_dump_counter")
    pco_dump_camera_memory = Component(EpicsSignal, "pco_dump_camera_memory")
    pco_max_imgs_seg0 = Component(EpicsSignalRO, "pco_max_imgs_seg0_RBV")
    pco_ready2acquire = Component(EpicsSignal, "pco_ready2acquire")
    pco_set_frame_rate = Component(EpicsSignal, "pco_set_frame_rate")
    

class MyHDF5Plugin(HDF5Plugin, FileStoreHDF5IterativeWrite):
    """adapt HDF5 plugin for AD 2.5+"""
    
    file_number_sync = None
    # FIXME:  .put() works OK but .value returns numpy object metadata
    # In [48]: pco_edge.hdf1.xml_layout_file.get()
    # Out[48]: '<array size=21, type=time_char>'
    xml_layout_file = Component(EpicsSignalWithRBV, "XMLFileName", string=True)
    xml_layout_valid = Component(EpicsSignalRO, "XMLValid_RBV")
    xml_layout_error_message = Component(EpicsSignalRO, "XMLErrorMsg_RBV", string=True)
    
    def get_frames_per_point(self):
        return self.parent.cam.num_images.get()
    

class MyPcoDetector(SingleTrigger, AreaDetector):
    """PCO detectors as used by 2-BM tomography"""
    # TODO: configure the "root" and "write_path_template" attributes
    
    cam = Component(MyPcoCam, "cam1:")
    image = Component(ImagePlugin, "image1:")
    hdf1 = Component(
        MyHDF5Plugin, 
        "HDF1:", 
        root="/",                   # root path for HDF5 files (for databroker filestore)
        write_path_template="/tmp", # path for HDF5 files (for EPICS area detector)
        )


class SynApps_saveData_Device(Device):
    """
    saveData support, just the fields used here
    
    USAGE::

        savedata = SynApps_saveData_Device("2bmb:saveData" name="savedata")
        savedata.scan_number.put(5)
        savedata.base_name.put("bane name")

    """

    scan_number = Component(EpicsSignal, "_scanNumber")
    base_name = Component(EpicsSignal, "_baseName")


class SynApps_Record_asub(Device):
    """asub record, just the fields used here"""
    # https://wiki-ext.aps.anl.gov/epics/index.php/RRM_3-14_Array_Subroutine
    
    proc = Component(EpicsSignal, ".PROC")
    a = Component(EpicsSignal, ".A")
    b = Component(EpicsSignal, ".B")
    vale = Component(EpicsSignal, ".VALE")
