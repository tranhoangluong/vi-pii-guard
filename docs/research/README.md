# Hướng nghiên cứu (bản nháp cho luận văn)

Tài liệu này ghi các câu hỏi nghiên cứu mà repo được thiết kế để trả lời. Đây là bản nháp để
trao đổi với giảng viên hướng dẫn, chưa phải đề cương chính thức.

## Bối cảnh

- Luật Bảo vệ dữ liệu cá nhân (Luật số 91/2025/QH15) có hiệu lực từ 01/01/2026. Nghị định
  330/2026/NĐ-CP quy định xử phạt, có hiệu lực từ 19/08/2026.
- Doanh nghiệp ngày càng gửi văn bản của khách hàng lên API LLM, phần lớn đặt ở nước ngoài.
- Từ 01/07/2025, chính quyền địa phương còn hai cấp (bỏ cấp huyện), nên định dạng địa chỉ thay
  đổi. Model học trên dữ liệu cũ có thể kém đi với địa chỉ mới (data drift).

## Công trình liên quan cần đọc và trích dẫn

- `vipii` (PyPI): thư viện phát hiện PII tiếng Việt bằng regex kết hợp NER. Có thể dùng làm baseline.
- OpenMed PII Vietnamese: các model token classification cho PII tiếng Việt, hướng y tế.
- Meddies-PII: bộ dữ liệu tổng hợp đa ngôn ngữ (có tiếng Việt) cho khử định danh văn bản y tế.
- Microsoft Presidio: kiến trúc recognizer + context, chủ yếu cho tiếng Anh.

## Câu hỏi nghiên cứu

1. **Rule, NER hay kết hợp?** Với từng loại PII, phương pháp nào cho tỉ lệ rò rỉ (leak rate)
   thấp nhất ở cùng mức false positive?
2. **Dữ liệu tổng hợp có đủ không?** Model train hoàn toàn trên dữ liệu tổng hợp đạt bao nhiêu
   trên một tập test gán nhãn tay từ văn bản trông như thật? Cách sinh dữ liệu nào (template,
   LLM viết lại, trộn) thu hẹp khoảng cách tốt nhất?
3. **Drift địa chỉ sau 2025:** model train với định dạng cũ (`--train-address-format pre_2025`)
   giảm bao nhiêu trên `test_post_2025.jsonl`? Cần bao nhiêu mẫu mới để phục hồi?
4. **Không dấu và viết thường:** hiệu năng giảm bao nhiêu với văn bản gõ không dấu (`nd01`, `nd02`)?
5. **Chi phí:** latency p95 của chế độ rule-only và hybrid trên CPU, so với thời gian gọi LLM.

## Thước đo

- Precision, recall, F1 theo từng loại, cả exact match và overlap match.
- **Char leak rate**: tỉ lệ ký tự PII vẫn lọt đến LLM (không phân biệt nhãn). Đây là thước đo
  chính về quyền riêng tư.
- **Entity leak rate**: tỉ lệ thực thể không bị che ký tự nào.
- Tỉ lệ văn bản không có PII nhưng bị che nhầm (ảnh hưởng chất lượng câu trả lời).
- Latency p50/p95.

## Kế hoạch thí nghiệm

| Bước | Lệnh | Kết quả |
|---|---|---|
| Baseline rule | `scripts/evaluate.py --data data/synthetic/test.jsonl --name rules` | `reports/rules.md` |
| Train NER | `scripts/train_ner.py --train ... --dev ...` | `models/xlmr-pii` |
| Hybrid | `scripts/evaluate.py --ner-model models/xlmr-pii --name hybrid` | `reports/hybrid.md` |
| Drift | `generate_data.py --train-address-format pre_2025`, train, rồi evaluate trên `test_post_2025.jsonl` | so sánh với `test_pre_2025.jsonl` |
| Tập test thật | tự gán nhãn khoảng 1.000 câu từ văn bản công khai, không chứa dữ liệu thật của ai | `data/gold/test.jsonl` |

## Lưu ý đạo đức và pháp lý

- Không thu thập hay commit dữ liệu cá nhân thật. Tập test "trông như thật" phải được viết lại
  bằng giá trị giả.
- Kết quả trên dữ liệu tổng hợp sinh từ cùng template với rule là lạc quan; luôn báo cáo kèm
  tập test gán nhãn tay.
