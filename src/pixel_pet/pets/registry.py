import os

from .models import PetAction, PetProfile


NILA_PROFILE = PetProfile(
    key="nila",
    name="Nila",
    idle_action="sit_idle_tail",
    actions=(
        PetAction(
            key="sit_idle_tail",
            label="Idle Tail",
            asset_path="assets/nila/sit-idle-tail",
            duration=2.0,
            category="idle",
            description="Default idle sit animation with tail movement.",
        ),
        PetAction(
            key="sit_licking",
            label="Sit Licking",
            asset_path="assets/nila/sit-licking",
            duration=3.0,
            category="calm",
            description="A short self-grooming sit animation.",
        ),
        PetAction(
            key="laydown_licking",
            label="Lay Down Licking",
            asset_path="assets/nila/laydown-licking",
            duration=3.0,
            category="calm",
            description="A relaxed lying-down animation that works well as a sleep-like state.",
        ),
        PetAction(
            key="laydown_meow",
            label="Lay Down Meow",
            asset_path="assets/nila/laydown-meow",
            duration=3.0,
            category="vocal",
            description="A sleepy low-energy meow while lying down.",
        ),
        PetAction(
            key="laydown_idle",
            label="Lay Down Idle",
            asset_path="assets/nila/laydown-idle",
            duration=4.0,
            category="rest",
            description="A quiet lying-down idle state for relaxed moments.",
        ),
        PetAction(
            key="laydown_sleeping",
            label="Lay Down Sleeping",
            asset_path="assets/nila/laydown-sleeping",
            duration=6.0,
            category="sleep",
            description="A deeper sleep animation for long calm stretches.",
        ),
        PetAction(
            key="sit_lookup_meow",
            label="Look Up Meow",
            asset_path="assets/nila/sit-lookup-meow",
            duration=4.0,
            category="attention",
            description="Looks up and meows for attention.",
        ),
        PetAction(
            key="sit_yawning",
            label="Sit Yawning",
            asset_path="assets/nila/sit-yawning",
            duration=3.0,
            category="sleep",
            description="A yawn that helps transition into rest or sleep.",
        ),
        PetAction(
            key="sit_tap_screen",
            label="Tap Screen",
            asset_path="assets/nila/sit-tap-screen",
            duration=4.0,
            category="nudge",
            description="Taps the screen as a direct productivity nudge.",
        ),
        PetAction(
            key="sit_tapping_bottom",
            label="Bottom Tap",
            asset_path="assets/nila/sit-tapping-bottom",
            duration=4.0,
            category="nudge",
            description="Animated tap toward the lower part of the screen.",
        ),
    ),
)


PET_PROFILES = {
    NILA_PROFILE.key: NILA_PROFILE,
}


def get_current_pet_key():
    pet_key = os.getenv("PIXEL_PET_KEY", "nila").strip().lower()

    if pet_key in PET_PROFILES:
        return pet_key

    return "nila"


def get_pet_profile(pet_key):
    return PET_PROFILES[pet_key]


def get_current_pet_profile():
    return get_pet_profile(get_current_pet_key())


def list_pet_profiles():
    return list(PET_PROFILES.values())


def get_action_map(pet_key=None):
    profile = (
        get_pet_profile(pet_key)
        if pet_key
        else get_current_pet_profile()
    )
    return {
        action.key: action
        for action in profile.actions
    }


def get_idle_asset_path(pet_key=None):
    profile = (
        get_pet_profile(pet_key)
        if pet_key
        else get_current_pet_profile()
    )
    idle_action = get_action_map(profile.key)[profile.idle_action]
    return idle_action.asset_path
