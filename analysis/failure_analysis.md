# Failure Analysis — Lab 18: Production RAG

**Học viên:** Ngô Minh Trí — 2A202602993 · **Ngày:** 04/10/2026

## Kết quả API thật

Production: 20 câu, 80/80 metric hợp lệ, `evaluation_status=completed`. Baseline: 20 câu, 79/80 metric hợp lệ, `evaluation_status=partial`; một điểm NaN được thay bằng 0 theo fallback. Vì vậy các giá trị baseline và Δ dưới đây còn giới hạn này, chưa phải so sánh hoàn toàn đầy đủ.

| Metric | Baseline | Production | Δ |
|---|---:|---:|---:|
| faithfulness | 0.7350 | 0.8139 | +0.0789 |
| answer_relevancy | 0.4679 | 0.5385 | +0.0705 |
| context_precision | 0.9333 | 0.9667 | +0.0333 |
| context_recall | 0.9000 | 0.9500 | +0.0500 |

## Bottom-5 theo trung bình bốn metric

Chẩn đoán tự động chỉ là gợi ý từ metric thấp nhất; phần review bên dưới đối chiếu output và context để tránh gán mọi faithfulness thấp thành hallucination.

### #1

- **Question:** Nhân viên thử việc có được hưởng bảo hiểm sức khỏe PVI không?
- **Expected:** KHÔNG. Nhân viên thử việc chưa được hưởng gói bảo hiểm sức khỏe PVI. Chỉ được tham gia bảo hiểm xã hội bắt buộc.
- **Got:** Không tìm thấy.
- **Mean score:** 0.5000
- **Worst metric:** faithfulness = 0.0000
- **Auto diagnosis:** LLM hallucinating
- **Context sources:** # Chính sách thử việc; # Chính sách bảo hiểm sức khỏe
- **Error Tree:** Output không trả lời → Context chứa quy định PVI? Có → Query rõ? Có → Generation từ chối sai.
- **Review/root cause:** Context thử việc ghi rõ chưa được hưởng PVI; đây là abstention sai, không phải bịa thông tin.
- **Suggested fix:** Prompt cần phân biệt phủ định rõ ràng với thiếu bằng chứng; thêm regression test cho câu hỏi quyền lợi thử việc.

### #2

- **Question:** Nhân viên tạm ứng 15 triệu, sau 20 ngày mới thanh toán. Bị phạt bao nhiêu?
- **Expected:** Thời hạn thanh toán là 15 ngày. Quá hạn 5 ngày, bị tính phí 2%/tháng trên 15.000.000 VNĐ = 300.000 VNĐ/tháng (tính pro-rata khoảng 50.000 VNĐ cho 5 ngày).
- **Got:** Nhân viên tạm ứng 15 triệu và sau 20 ngày mới thanh toán. Thời gian quá hạn là 5 ngày (20 - 15). Phí phạt là 2%/tháng, tức là 0.067%/ngày.

Tính phí phạt:
15.000.000 VNĐ * 0.067% * 5 ngày = 5.025 VNĐ.

Nhân viên sẽ bị phạt 5.025 VNĐ.
- **Mean score:** 0.6245
- **Worst metric:** faithfulness = 0.1111
- **Auto diagnosis:** LLM hallucinating
- **Context sources:** # Chính sách tạm ứng
- **Error Tree:** Output số tiền sai → Context có tỷ lệ và thời hạn? Có → Phép tính đúng? Không → Generation/số học.
- **Review/root cause:** 2%/30 × 5 × 15 triệu = 50.000 VNĐ; output 5.025 VNĐ sai cả so với chính biểu thức đã viết.
- **Suggested fix:** Dùng hàm tính toán xác định hoặc tool calculator; kiểm tra đơn vị phần trăm và giả định 30 ngày/tháng.

### #3

- **Question:** Muốn mua thiết bị trị giá 55 triệu cần ai phê duyệt?
- **Expected:** Đơn hàng trên 50.000.000 VNĐ cần Tổng Giám đốc (CEO) phê duyệt.
- **Got:** Cần Tổng Giám đốc (CEO) phê duyệt.
- **Mean score:** 0.7278
- **Worst metric:** answer_relevancy = 0.4110
- **Auto diagnosis:** Answer doesn't match question
- **Context sources:** # Chính sách tạm ứng; # Quy trình mua sắm
- **Error Tree:** Output đúng CEO → Context đúng? Có → Metric relevancy thấp → Kiểm tra evaluator trước sửa retrieval.
- **Review/root cause:** Đáp án đúng theo ground truth; câu trả lời ngắn có thể tạo hypothetical question không khớp đủ ý. Chưa có bằng chứng lỗi answer.
- **Suggested fix:** Kiểm tra điểm relevancy bằng human review; thử nêu ngưỡng trên 50 triệu và nguồn phê duyệt.

### #4

- **Question:** Nhân viên được tài trợ khóa học 25 triệu, nghỉ việc sau 8 tháng hoàn thành khóa học. Phải hoàn trả bao nhiêu?
- **Expected:** Nhân viên phải cam kết làm việc ít nhất 1 năm sau khi hoàn thành khóa học. Nghỉ sau 8 tháng là trước hạn cam kết, phải hoàn trả 100% chi phí tức 25.000.000 VNĐ.
- **Got:** Nhân viên phải hoàn trả **100% chi phí** đào tạo đã được tài trợ, tức là **25 triệu VNĐ**.
- **Mean score:** 0.7296
- **Worst metric:** answer_relevancy = 0.4185
- **Auto diagnosis:** Answer doesn't match question
- **Context sources:** # Chính sách hoàn chi đào tạo; # Chính sách đào tạo nội bộ
- **Error Tree:** Output đúng 25 triệu → Context đúng? Có → Nêu đủ điều kiện 8 tháng/1 năm? Chưa → Explanation/relevancy.
- **Review/root cause:** Kết quả hoàn trả đúng; lời giải chưa nói rõ nghỉ trước thời hạn cam kết một năm.
- **Suggested fix:** Nêu căn cứ 8 tháng < 12 tháng nên hoàn trả 100%, giữ kết quả 25 triệu.

### #5

- **Question:** Nghỉ phép không lương 20 ngày cần ai phê duyệt?
- **Expected:** Nghỉ 16-30 ngày cần phê duyệt của Giám đốc điều hành (CEO). Lưu ý: nghỉ trên 14 ngày không lương, nhân viên phải tự đóng phần bảo hiểm của mình.
- **Got:** Nghỉ phép không lương 20 ngày cần phê duyệt của **Giám đốc điều hành (CEO)**.
- **Mean score:** 0.7308
- **Worst metric:** answer_relevancy = 0.4231
- **Auto diagnosis:** Answer doesn't match question
- **Context sources:** # Chính sách nghỉ phép không lương; # Chính sách nghỉ phép năm (Phiên bản 2024); # Chính sách nghỉ phép năm (Phiên bản 2023)
- **Error Tree:** Output đúng CEO → Context đúng? Có → Nêu điều kiện 16–30 ngày và bảo hiểm? Chưa → Completeness/evaluator.
- **Review/root cause:** Người phê duyệt đúng; ground truth còn lưu ý tự đóng bảo hiểm trên 14 ngày, nên cần phân biệt ý hỏi chính với thông tin bổ sung.
- **Suggested fix:** Nêu nhóm 16–30 ngày và lưu ý bảo hiểm; review thủ công trước xem điểm relevancy thấp là lỗi retrieval.

## Case study và ưu tiên một giờ tiếp theo

Chọn câu tính phí tạm ứng: retrieval đã đưa đúng chính sách, nhưng LLM tính sai. Việc thêm chunks không sửa được phép nhân. Ưu tiên calculator và regression test 15 triệu, quá hạn 5 ngày → 50.000 VNĐ theo giả định tháng 30 ngày. Tiếp theo sửa abstention về PVI, rồi human review ba câu trả lời đúng có relevancy thấp.

## Lỗi evaluator và cách khắc phục

Lượt RAGAS đồng thời ban đầu gặp `402 in_flight_budget_exhausted`. Giảm `RunConfig(max_workers=2)`, giới hạn output judge và đánh giá lại các câu trả lời đã lưu. Lượt production sau cùng không có request lỗi và đủ 80 metric. Baseline vẫn có một NaN, không coi điểm fallback đó là kết quả đo.
