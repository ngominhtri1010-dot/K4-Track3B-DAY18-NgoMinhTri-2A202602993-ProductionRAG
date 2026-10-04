# Kiểm tra bài nộp — 04/10/2026

| Hạng mục rubric | Bằng chứng / trạng thái |
|---|---|
| M1–M5 | Có implementation; bộ test đã đạt 39/39, gồm 2 tests tích hợp. |
| Pipeline | Đã chạy API thật 20 câu với model local, exit code 0; câu trả lời tại `reports/pipeline_answers.json`. |
| Báo cáo RAGAS | Production completed: 20 câu, 80/80 metrics; 3/4 metrics ≥ 0.70. Baseline partial: 79/80 metrics. |
| Failure analysis | Đã cập nhật bottom-5 theo RAGAS thật, có review và Error Tree. |
| Reflection | Có `reflection_NgoMinhTri.md` dạng bản nháp cần học viên xác nhận. |
| Combined enrichment | Đã chạy 117 chunks bằng API thật, không có lỗi enrichment. |
| Latency | Có `reports/latency_report.json`; số liệu pipeline đo API thật; evaluation có lượt retry với concurrency 2. |

## Thời gian từ báo cáo hiện có

| Bước | Thời gian |
|---|---:|
| Chunking | 0.034 s |
| Enrichment API | 406.497 s |
| Indexing | 11.143 s |
| Load reranker | 3.601 s |
| Retrieval trung bình/câu | 0.191 s |
| Reranking trung bình/câu | 0.473 s |
| Generation API trung bình/câu | 1.673 s |
| RAGAS production retry | 162.000 s |

Số đo API thật từ `reports/latency_report.json`; RAGAS có lượt đánh giá lại với concurrency 2.

## Các mục cần hoàn tất trước khi nộp

1. API key đã cấu hình và pipeline đã chạy. Baseline còn một metric NaN; cần kiểm tra nếu muốn so sánh đủ 80/80 metric.
2. Bảng so sánh và bottom-5 đã cập nhật; Δ baseline được ghi rõ giới hạn một điểm fallback.
3. Học viên đọc và xác nhận reflection, chỉnh kế hoạch theo project cá nhân thực tế.
4. Chạy lại `python check_lab.py` sau evaluation. Checker hiện chỉ kiểm tra file/keys và có thể báo sẵn sàng dù metrics chưa đo.
5. Đã xóa 19 dòng marker theo yêu cầu mới của học viên; số marker còn lại trong source là 0, đáp ứng tiêu chí tự động của rubric.
6. Kiểm tra thay đổi, commit và push repository public để nộp link theo yêu cầu lớp. Chưa thực hiện push trong phiên làm việc này.

`.env`, `.venv/` và artifact `:memory:.ses` được bỏ qua trong Git. Template reflection gốc vẫn được giữ để tham khảo.
