from src.pixel_pet.activity.events import ActivityEvent, ActivityEventType
from src.pixel_pet.trackers.base_tracker import BaseTracker


class CameraPresenceTracker(BaseTracker):
    name = "camera_presence_tracker"

    def __init__(
        self,
        camera_index=0,
        min_face_size=(60, 60),
        absence_confirmation_frames=15,
    ):
        self.camera_index = camera_index
        self.min_face_size = min_face_size
        self.absence_confirmation_frames = absence_confirmation_frames
        self._was_present = None
        self._missing_face_frames = 0
        self._cv2 = None
        self._camera = None
        self._face_cascade = None
        self._disabled = False

    def poll(self):
        if self._disabled:
            return []

        try:
            self._ensure_camera_ready()
        except RuntimeError as error:
            self._disabled = True

            return [
                ActivityEvent(
                    event_type=ActivityEventType.TRACKER_ERROR,
                    source=self.name,
                    payload={
                        "error": str(error),
                        "tracker": self.name,
                    },
                )
            ]

        ok, frame = self._camera.read()

        if not ok:
            self.close()
            self._disabled = True

            return [
                ActivityEvent(
                    event_type=ActivityEventType.TRACKER_ERROR,
                    source=self.name,
                    payload={
                        "error": "Could not read from camera.",
                        "tracker": self.name,
                    },
                )
            ]

        face_detected, face_count = self._detect_presence(frame)
        is_present = self._confirm_presence(face_detected)

        if is_present == self._was_present:
            return []

        self._was_present = is_present

        event_type = (
            ActivityEventType.USER_PRESENT
            if is_present
            else ActivityEventType.USER_ABSENT
        )

        return [
            ActivityEvent(
                event_type=event_type,
                source=self.name,
                payload={
                    "camera_index": self.camera_index,
                    "face_count": face_count,
                    "missing_face_frames": self._missing_face_frames,
                    "absence_confirmation_frames": (
                        self.absence_confirmation_frames
                    ),
                },
            )
        ]

    def close(self):
        if self._camera:
            self._camera.release()
            self._camera = None

    def _ensure_camera_ready(self):
        if self._camera:
            return

        try:
            import cv2
        except ImportError as error:
            raise RuntimeError(
                "OpenCV is required for camera tracking. "
                "Install it with: pip install opencv-python"
            ) from error

        self._cv2 = cv2
        self._camera = cv2.VideoCapture(self.camera_index)

        if not self._camera.isOpened():
            self._camera.release()
            self._camera = None
            raise RuntimeError("Could not open camera.")

        cascade_path = (
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"
        )
        self._face_cascade = cv2.CascadeClassifier(cascade_path)

        if self._face_cascade.empty():
            self.close()
            raise RuntimeError("Could not load face detection model.")

    def _detect_presence(self, frame):
        grayscale = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            grayscale,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=self.min_face_size,
        )

        face_count = len(faces)

        return face_count > 0, face_count

    def _confirm_presence(self, face_detected):
        if face_detected:
            self._missing_face_frames = 0
            return True

        self._missing_face_frames += 1

        if self._was_present is None:
            return False

        if self._missing_face_frames >= self.absence_confirmation_frames:
            return False

        return self._was_present
