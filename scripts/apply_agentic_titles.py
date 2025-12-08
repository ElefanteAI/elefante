
import chromadb
from src.utils.config import get_config

# MANUAL CURATION BY AGENTIC INTELLECT
# Format: Subject-Aspect-Qualifier (Max 30 chars)
TITLES = {
    "09a65aec-1573-4bb6-b4eb-9d381f5b2858": "Self-Identity-Architect",
    "1bc33098-7639-47ac-aeb4-8c343eff98fd": "Omega-Arch-Microservices",
    "68a83b98-f815-4425-ab0c-15312418ec0c": "Self-Identity-Location",
    "8c4603bf-23db-4c7e-94da-fd14f6ad689a": "Self-Identity-Location",
    "1d359020-9a22-4383-a306-2c986ce3b6fd": "Self-Pref-NoSmallTalk",
    "78eba993-12b5-4727-b1e4-166015412263": "Self-Skill-Polyglot",
    "611226a7-982f-4bde-8086-ee628bbb44e2": "User-Fact-ApiKey",
    "837c5abf-d0a0-4181-9e17-7af770aa52fb": "Project-Tech-Kuzu",
    "c7382745-cd3e-48d0-a301-9df3f70095e0": "Self-Pref-DarkMode",
    "987fbb0a-1d75-4098-b9f9-af3654d26237": "MCP-Failure-Timeouts",
    "2400aac6-6004-4424-906a-05c9e3da34db": "MCP-Fix-LazyLoading",
    "6f515776-344e-4177-bc7b-ce7576e53bdf": "dashboard-Tech-Stack",
    "521def76-7e91-473d-aebd-556abbb3698b": "Elefante-Arch-LLM",
    "1adca9fe-af98-43fe-89bb-daed755ae3e3": "User-Fact-ApiKey",
    "43642f2c-667e-41f5-b647-46454ec4b311": "Project-Tech-Kuzu",
    "8090d504-60f7-4608-b9db-46adde1422e0": "Self-Pref-DarkMode",
    "3ae3712c-cbd1-4016-af6d-c446dc8c45ce": "MCP-Failure-Timeouts",
    "e010d818-d039-4763-8ad5-06f3962e2cab": "MCP-Fix-LazyLoading",
    "8817e4d5-b6c2-4c1e-bd56-c43bea158dc7": "dashboard-Tech-Stack",
    "4d20dc7a-71b2-4145-92e7-b0ffb948636c": "Elefante-Arch-LLM",
    "69477a46-40b9-4025-9dcd-25add1f91b7a": "Test-Fact-Persistence",
    "a7c92f28-c5c9-4d75-9e14-7475917ecfd4": "Test-Fact-Graph",
    "1dbaa502-872d-4521-aa73-4674a6a9902f": "Test-Fact-NoScripts",
    "039fe8fa-336b-4431-bae6-4a1ecb76a37d": "Test-Fact-Persistence",
    "5d71714b-aedb-43bd-b87c-06cc376db25a": "Test-Fact-EntityRel",
    "db3b3fe8-2ab7-467e-a338-082904c00008": "Test-Fact-Hybrid0",
    "bf535b25-1507-4535-9cb2-e3eb99f0c503": "Test-Fact-Hybrid1",
    "aa8e8b06-41de-402e-90d1-0acc24405e4e": "Test-Fact-Hybrid2",
    "1efe8727-fe59-4552-85ca-6fb8a130c5c5": "Test-Fact-Startup",
    "9e478673-0be7-4e40-87cd-8ea4d366c894": "Elefante-Test-E2E1",
    "30c108c3-2ac6-4be2-86ae-e370132ea0f0": "Elefante-Test-E2E2",
    "ed61447c-1b0f-47ac-b908-87ee88fbfb5e": "Elefante-Test-E2E3",
    "bb0fe478-afb0-4556-9e27-cbe887baf170": "Self-Pref-CleanCode",
    "8c7be853-9a4c-4735-a681-37f260384666": "DevEtiquette-Avoid-Redundant",
    "d2de9655-236b-42fa-af6e-093a8d79a296": "Self-Value-BestPractices",
    "c5e8845e-dd3b-48ae-94b1-8406155dd6c3": "DevEtiquette-Rule-Relevance",
    "a87b7a2d-2099-4c12-9844-48618eb7dc6a": "Agent-Rule-CriticalDebug",
    "b367d32c-7b49-41e9-90b9-38b824354228": "Test-Fact-MetaPersist",
    "b6f6f97c-9b6f-47e2-8b3d-71b3152d5bcf": "Test-Fact-MetaPersist",
    "b3c1d93e-2f22-4876-8f2e-4b7119e71277": "Self-Identity-SovereignArch",
    "485f8f87-1e5b-427a-8fba-7d46101c59bb": "Agent-Protocol-Brutalist",
    "e42bf689-1304-4531-bc60-d636400ac591": "Sys-Kernel-UserRole",
    "4b7f8f90-8c2d-4521-9e8a-36109f582b1c": "Self-Pref-TokenOptim",
    "9e2b1d7f-3c5a-4b6e-8d9f-a123bc4d5e6f": "Self-Limit-DocFirst",
    "c3e1e1e1-e1e1-4e1e-1e1e-e1e1e1e1e1e1": "Self-Pref-HatePython",
    "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d": "Self-Pref-HatePython",
    "99999999-9999-9999-9999-999999999999": "Self-Pref-HatePython",
    "88888888-8888-8888-8888-888888888888": "Self-Pref-HatePython",
    "77777777-7777-7777-7777-777777777777": "Self-Pref-HatePython",
    "66666666-6666-6666-6666-666666666666": "Self-Pref-HatePython",
    "55555555-5555-5555-5555-555555555555": "Self-Pref-HatePython",
    "35058728-6623-4560-85f0-519b5b29ecb0": "Agent-Rule-IncludeUser",
    "1df956e8-5173-4c99-ad03-3dc8497d7f8f": "Agent-Rule-ConnectMem",
    "3b4b4ba1-2c83-41b1-ba45-b3da157ec691": "Self-Pref-ConciseComms",
    "45f0cc09-81e6-48fe-ac6c-2885e4ac04fc": "Self-Pref-NoTestScripts",
    "8729d5fa-9eea-4402-a777-6eeb2c7687bc": "Self-Pref-NoTestScripts",
    "0b51b39e-a122-41a2-9d04-ff3d6ce194b8": "Build-Pitfall-HardRefresh",
    "939cacd2-c7e9-4ea9-84d4-c5c63fd4279f": "Build-Pitfall-UpdateData",
    "455a3fbe-5733-4bd0-94aa-e4716634bf97": "Build-Pitfall-Frontend",
    "fa801cb9-0cbf-4b69-801f-d4de6c3f8bab": "Agent-Protocol-PreCheck",
    "96a5aa12-ac65-4e26-9b3f-e887463ceb88": "Elefante-Method-FirstUse",
    "7cbfa09d-e75f-4ae1-9160-039f87b1d9f7": "Kuzu-Pitfall-ExistingDir",
    "beeba65d-7cdf-4778-937d-a5ce449c4071": "MCP-Rule-SearchFirst",
    "fdfcb2ac-5de7-4ff0-a0ed-9edf221f8f08": "Self-Identity-Elefante",
    "b27c0f32-a09a-4d2c-b3a6-741246fcc2be": "Self-Identity-Elefante",
    "f13f171c-0cd8-4681-ad39-7fd223eda897": "Self-Identity-Elefante",
    "ed4a5105-b04e-4a42-b3f2-a8a1e661e57b": "Elefante-Goal-Bootstrap",
    "157b55e0-a617-45f5-9e71-a83869444c38": "Self-Identity-MatrixArch",
    "d25ce4e2-4733-427b-af1e-32208c0fe8f2": "Self-Pref-SafeMode",
    "3250c6e5-4bcb-4da1-8d02-801a90a92e73": "Self-Pref-SafeMode",
    "8396a07d-10c0-40f7-9348-c662b08c15d6": "Self-Pref-SafeMode",
    "877979d6-58aa-400a-878c-80fe9ca2c02e": "Elefante-Method-Plasticity",
    "d39742cf-f11b-4e25-8f9b-a0326add0c3f": "MCP-Rule-StdoutPurity",
    "5c54f882-fddb-44ed-9a9a-dc9e19751581": "Elefante-Fact-SelfRepair",
    "c12126c1-d564-4806-a7cb-7c2e7a440da7": "MCP-Rule-Law6Corollary",
    "12cffdf2-a4a7-4310-8619-a8768fe45381": "Self-Identity-Reflection",
    "9c8dc313-e7b4-4a05-beb4-850e2f5d7bff": "Debug-Rule-FailAnalysis",
    "fb435c56-8eeb-40ee-95aa-37e4a7e68810": "Kuzu-Fact-FixVerified",
    "aef00bdd-7ff2-4490-87bf-5f4a3d67262e": "Self-Pref-RustVsPython",
    "24ec0fbe-9258-496c-9920-993b935bbc26": "Self-Goal-HighValuation"
}

def apply_titles():
    print(f"Applying {len(TITLES)} semantic titles...")
    config = get_config()
    client = chromadb.PersistentClient(path=config.elefante.vector_store.persist_directory)
    collection = client.get_collection("memories")

    updated = 0
    for mem_id, title in TITLES.items():
        try:
            # Check if memory exists
            existing = collection.get(ids=[mem_id])
            if not existing["ids"]:
                print(f"Skipping {mem_id[:8]} (not found)")
                continue

            # Update metadata
            meta = existing["metadatas"][0]
            meta["title"] = title
            collection.update(ids=[mem_id], metadatas=[meta])
            updated += 1
        except Exception as e:
            print(f"Error updating {mem_id}: {e}")

    print(f"✅ Successfully updated {updated} memory titles")

if __name__ == "__main__":
    apply_titles()
