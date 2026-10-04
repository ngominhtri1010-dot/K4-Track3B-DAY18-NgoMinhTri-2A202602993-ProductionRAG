# Reflection — Ngô Minh Trí

**MSSV:** 2A202602993 · **Khóa:** K4 Track 3B · **Ngày:** 04/10/2026

Đây là bản nháp dựa trên code và kết quả kiểm tra của repository. Học viên cần đọc, xác nhận trải nghiệm cá nhân và điều chỉnh kế hoạch trước khi nộp. 


## 1. Lecture mapping

| Concept | Module / Hàm | Quan sát từ implementation |
|---|---|---|
| Semantic chunking | M1 `chunk_semantic()` | So sánh cosine giữa hai câu liền kề; threshold mặc định 0.85. Model MiniLM được cache; chưa ghi nhận bảng A/B định lượng vào report. |
| Hierarchical chunking | M1 `chunk_hierarchical()`, pipeline `run_query()` | Parent 2048, child 256 ký tự. Retrieve child rồi dùng parent gốc làm context, gộp các parent trùng nhau. |
| BM25 + Dense fusion | M2 `reciprocal_rank_fusion()` | RRF dùng 1/(60 + rank + 1); không cộng trực tiếp điểm BM25 và cosine. BGE-M3 chạy local, Qdrant có fallback in-memory. |
| Cross-encoder | M3 `CrossEncoderReranker.rerank()` | BGE-reranker-v2-m3 chấm cặp query/document, lấy top-3. Rerank nội dung gốc thay vì summary/câu hỏi sinh thêm. |
| RAGAS | M4 `evaluate_ragas()`, `failure_analysis()` | Có 4 metrics và diagnosis theo metric thấp nhất. Lần API production đạt faithfulness 0.814, relevancy 0.538, precision 0.967, recall 0.950. |
| Contextual embeddings | M5 `_enrich_single_call()` | Một request/chunk sinh summary, HyQA, context và metadata. Text embed chứa enrichment; source và parent_id gốc được giữ lại. |

## 2. Khó khăn và cách xử lý

Lần chạy offline trước khi cấu hình provider xuất hiện lỗi:

```text
Did not find openai_api_key, please add an environment variable `OPENAI_API_KEY` which contains it, or pass `openai_api_key` as a named parameter.
```

Kiểm tra report cho thấy không có kết quả từng câu, nên không được coi fallback 0 là điểm đo. Cấu hình hiện truyền endpoint và key rõ ràng cho cả ChatOpenAI và OpenAIEmbeddings của RAGAS; OpenRouter cần model ID có tiền tố nhà cung cấp. Đã chạy API thực tế. Lỗi `402 in_flight_budget_exhausted` được xử lý bằng giảm số request đánh giá đồng thời xuống 2. Production đạt 80/80 điểm hợp lệ; baseline 79/80.

Vấn đề tích hợp khác là parent chunks ban đầu bị bỏ sau indexing. Pipeline đã lưu mapping parent_id → parent text, giữ original_text trong metadata và dùng mapping khi dựng context. Test tích hợp xác nhận hai child cùng parent chỉ tạo một context.

Kiến thức cần bổ sung: quản lý vòng đời phiên bản tài liệu, truy vấn đa ý, giới hạn/rate limit của provider và phân biệt lỗi evaluator với lỗi retrieval. Review API cho thấy một lỗi tính phí và một abstention sai; một số câu trả lời đúng vẫn có relevancy thấp, cần review evaluator.

## 3. Kế hoạch áp dụng

**Project dự kiến:** Trợ lý tra cứu chính sách nội bộ dựa trên repository này; chưa giả định học viên đã có project khác.

Hiện trạng: hierarchical → enrichment → hybrid retrieval → rerank → parent context → answer → evaluation. Các câu hỏi về phép năm có thể chọn phiên bản cũ; câu hỏi kết hợp phép năm/lương thiếu nguồn thứ hai.

1. Giữ hierarchical làm mặc định; thử structure-aware để bảo toàn bảng và đánh giá trên cùng bộ câu hỏi.
2. Thêm metadata ngày hiệu lực và phiên bản hiện hành; thử tách query đa ý trước hybrid search.
3. Giữ cross-encoder và đo trade-off top-k với latency đã ghi trong `reports/latency_report.json`.
4. Chạy RAGAS thật trên 20 câu; thêm kiểm tra số học và phủ định cho các câu nghiệp vụ.
5. So sánh combined enrichment với raw chunks, ghi chất lượng và số API calls trước khi chọn phương án.

**Tuần 1 (05–11/10/2026):** chạy API evaluation, hoàn thiện bottom-5, thử lọc phiên bản và thêm tests cho câu hỏi lịch sử/hiện hành.

**Tuần 2 (12–18/10/2026):** thử query decomposition, A/B enrichment, đo latency và chọn cấu hình theo chất lượng/chi phí.
