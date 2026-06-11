from app.analyzers.duplication import DuplicationAnalyzer
from tests.conftest import make_file


def test_cross_file_duplication_detected():
    dup = """
def process(items):
    result = []
    for i, item in enumerate(items):
        if item > 0:
            result.append(item * 2)
        else:
            result.append(item * 3)
    return sum(result) / len(result)
"""
    unique = """
def transform(payload):
    bucket = {}
    for key in payload:
        bucket[key] = payload[key] ** 2
    return bucket
"""
    a = make_file("a.py", dup)
    b = make_file("b.py", dup)
    c = make_file("c.py", unique)
    result = DuplicationAnalyzer().analyze([a, b, c], {})
    scores = {r.path: r.score for r in result.file_results}
    assert scores["a.py"] > scores["c.py"]
    assert scores["b.py"] > scores["c.py"]


def test_scaffold_pairs_not_flagged_as_cross_duplication():
    og_image = """
import { ImageResponse } from "next/og";
export const alt = "Profile";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export default async function Image({ params }) {
    const data = await fetch(`https://api.example.com/agent/${params.id}`);
    const profile = await data.json();
    return new ImageResponse(
        <div style={{ display: "flex", background: "#0a0a0a", width: "100%" }}>
            <h1>{profile.name}</h1>
            <p>{profile.score}</p>
        </div>,
        { width: 1200, height: 630 }
    );
}
"""
    a = make_file("app/agent/[id]/opengraph-image.tsx", og_image, language="tsx")
    b = make_file("app/agent/[id]/twitter-image.tsx", og_image, language="tsx")
    result = DuplicationAnalyzer().analyze([a, b], {})
    by_path = {r.path: r for r in result.file_results}
    for r in by_path.values():
        assert r.details.get("scaffold") is True
        # Cross-file similarity is still measured and reported…
        assert r.details["max_cross_jaccard"] > 0.9
        # …but does not count toward the debt score.
        assert r.score < 20


def test_real_files_still_flagged():
    dup = """
def handler_one(request):
    payload = request.json()
    if not payload.get("id"):
        return error_response("missing id", 400)
    record = lookup(payload["id"])
    if record is None:
        return error_response("not found", 404)
    record.update(payload)
    save(record)
    return success_response(record)
"""
    a = make_file("api/users.py", dup)
    b = make_file("api/orders.py", dup)
    result = DuplicationAnalyzer().analyze([a, b], {})
    for r in result.file_results:
        assert r.details.get("scaffold") is None
        assert r.score > 50
