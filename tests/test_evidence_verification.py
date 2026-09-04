from text_as_data.extraction import verify_evidence_span


def test_exact_substring_match_is_verified_as_exact():
    verified, tier = verify_evidence_span("about 200 people occupied the square", "Yesterday, about 200 people occupied the square in front of city hall.")
    assert verified is True
    assert tier == "exact"


def test_curly_quotes_and_em_dash_still_verify_as_normalized():
    document = "The mayor said “this will not stand” — a clear escalation."
    span = "\"this will not stand\" - a clear escalation"
    verified, tier = verify_evidence_span(span, document)
    assert verified is True
    assert tier == "normalized"


def test_collapsed_whitespace_and_case_still_verify_as_normalized():
    document = "The   protest   spread   to    three   other   cities overnight."
    span = "the protest spread to three other cities"
    verified, tier = verify_evidence_span(span, document)
    assert verified is True
    assert tier == "normalized"


def test_fabricated_span_not_found_in_document_fails():
    verified, tier = verify_evidence_span("the union called for a general strike", "About 200 people occupied the square in front of city hall.")
    assert verified is False
    assert tier == "not_found"


def test_empty_span_fails_as_empty():
    verified, tier = verify_evidence_span("", "About 200 people occupied the square.")
    assert verified is False
    assert tier == "empty"


def test_whitespace_only_span_fails_as_empty():
    verified, tier = verify_evidence_span("   ", "About 200 people occupied the square.")
    assert verified is False
    assert tier == "empty"


def test_span_too_short_after_normalization_fails_as_too_short():
    # "The Cat" is not a literal substring of the document (so the exact
    # tier can't match), and its normalized form ("the cat", 7 characters)
    # is under the 8-character cutoff -- too short to trust as
    # distinguishing evidence even before attempting the normalized
    # substring search, mirroring QualiHolo's own short-span cutoff.
    verified, tier = verify_evidence_span("The Cat", "The mayor made a statement about the protest.")
    assert verified is False
    assert tier == "too_short"


def test_near_miss_paraphrase_is_not_verified_even_though_it_is_similar():
    # Never falls back to fuzzy/similarity matching -- a near-miss is a
    # failure, on purpose (this is the whole point of the check).
    document = "About 200 demonstrators occupied the square in front of city hall."
    span = "about 200 people occupied the square near city hall"
    verified, tier = verify_evidence_span(span, document)
    assert verified is False
    assert tier == "not_found"
