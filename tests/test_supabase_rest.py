from radar.supabase_rest import Supabase


def test_cle_secrete_nouvelle_generation_pas_en_bearer() -> None:
    s = Supabase("https://x.supabase.co/", "sb_secret_abc")
    assert s._headers["apikey"] == "sb_secret_abc"  # pyright: ignore[reportPrivateUsage]
    assert "Authorization" not in s._headers  # pyright: ignore[reportPrivateUsage]


def test_ancienne_cle_jwt_en_bearer() -> None:
    s = Supabase("https://x.supabase.co", "eyJhbGciOi.jwt")
    assert s._headers["Authorization"] == "Bearer eyJhbGciOi.jwt"  # pyright: ignore[reportPrivateUsage]
