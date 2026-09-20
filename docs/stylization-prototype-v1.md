# Stylization Prototype v1 — kiểm tra identity preservation

Thử nghiệm này trả lời một câu hỏi kỹ thuật cụ thể, tách biệt khỏi việc làm nghệ thuật cuối
cùng: **nếu ta nén tỉ lệ nhân vật xuống phong cách "soft chibi anime" (~3.5–4 đầu), hai người
có silhouette/khuôn mặt khác nhau có còn đọc được là hai người khác nhau không?** Nếu không,
toàn bộ hướng character system (base mesh thật → morph theo dữ liệu → stylize) sẽ hỏng ở khâu
cuối cùng, bất kể mesh gốc tốt đến đâu.

Script: `tools/blender/generate_stylization_prototype.py`. Chạy:

```
blender --background --python tools/blender/generate_stylization_prototype.py -- \
    --outdir assets/characters/stylization_prototype
```

## Thiết lập test

Hai nhân vật cố tình đặt ở hai thái cực (`CHARACTERS` trong script):

| | A | B |
|---|---|---|
| height | 1.60 m | 1.90 m |
| shoulder | hẹp (0.85×) | rộng (1.15×) |
| body_fat | cao (0.75) | thấp (0.15) |
| leg_length | ngắn (0.85×) | dài (1.15×) |
| face_width | rộng (1.25×) | hẹp (0.80×) |

Cả hai được dựng bằng **cùng một hàm** `compute_realistic_joints()` — chỉ khác tham số đầu
vào, giống hệt cách hai người dùng thật với dữ liệu scan khác nhau sẽ tạo ra hai mesh khác
nhau trong hệ thống thật.

## Phép biến đổi stylization

`stylize()` áp **cùng một công thức** lên cả hai nhân vật (`STYLIZE` dict):

- Phóng to đầu 1.55× (freely stylized, đúng tinh thần "soft chibi")
- Nén chiều cao thân+chân sao cho tổng chiều cao / chiều cao đầu = 3.75 (trong khoảng 3.5–4
  spec yêu cầu)
- Chỉ giữ lại 88% độ lệch ngang (X) so với bản thật — **cố ý không nén ngang theo cùng tỉ lệ
  với chiều dọc**, để vai rộng/hẹp và mặt rộng/hẹp vẫn còn phân biệt được sau khi nén dọc mạnh
- Tăng nhẹ độ tròn trịa toàn thân (`girth_boost`) cho cảm giác "soft"

Vì hai nhân vật dùng chung một công thức biến đổi, **tỉ lệ khác biệt giữa A và B được bảo toàn
gần như tuyệt đối theo toán học** — đây không phải là điều cần "hy vọng đúng", mà là hệ quả
trực tiếp của việc áp cùng một affine transform. Điều thực sự cần quan sát bằng mắt là: sau
khi nén xuống 3.5–4 đầu, khác biệt đó có còn *nhìn thấy được* không, hay bị nuốt mất bởi hình
dạng chibi tròn trịa.

## Kết quả đo được

`assets/characters/stylization_prototype/identity_preservation_report.json`:

| Chỉ số | A thật | B thật | Tỉ lệ A/B | A stylized | B stylized | Tỉ lệ A/B |
|---|---|---|---|---|---|---|
| Chiều cao | 1.586 m | 1.884 m | 0.842 | 1.249 m | 1.483 m | 0.842 |
| Độ rộng vai | 0.289 m | 0.391 m | 0.739 | 0.254 m | 0.344 m | 0.738 |
| Độ rộng mặt | 0.288 m | 0.184 m | 1.565 | 0.499 m | 0.319 m | 1.564 |
| Độ dài chân | 0.684 m | 1.042 m | 0.656 | 0.457 m | 0.696 m | 0.656 |
| Tỉ lệ đầu/thân | 7.38 | 7.38 | — | 3.75 | 3.75 | — |

Tỉ lệ A/B gần như không đổi trước/sau stylize ở mọi chỉ số — đúng như kỳ vọng toán học ở trên.
Bằng mắt (xem ảnh dưới), khác biệt vẫn đọc được rõ dù cả hai đã co về 3.75 đầu.

## Ảnh render

- `comparison_all.png` — cả 4: A thật, A stylized, B thật, B stylized
- `comparison_A_before_after.png`, `comparison_B_before_after.png` — trước/sau của từng người
- `comparison_stylized_only.png` — **ảnh quan trọng nhất**: A stylized cạnh B stylized, cùng
  art style, để đánh giá "đây có phải hai người khác nhau không" bằng mắt thường

## Bốn identity anchor — trạng thái sau prototype này

1. **Head shape** — mô hình hoá được bề rộng đầu (`face_width_scale` → bán kính đầu theo trục
   X); mặt dài/tròn theo chiều dọc và các đặc điểm hình học khác (gò má, hàm...) chưa có vì
   placeholder chưa có topology đầu chi tiết — cần base mesh thật từ hoạ sĩ.
2. **Eye configuration** — **chưa làm được** ở prototype này, vì placeholder không có hình học
   mắt. Cần lặp lại test này trên base mesh thật một khi có landmark mắt (spacing, height,
   width, angle, depth) để xác nhận phép nén dọc 3.5–4 đầu không làm méo vị trí mắt tương đối.
3. **Body silhouette** — đã test trực tiếp, xem bảng trên: vai rộng/hẹp, chân dài/ngắn giữ
   đúng tỉ lệ tương đối.
4. **Height/proportion** — đã test: A và B **không** bị chuẩn hoá về cùng một chiều cao,
   chênh lệch giữ nguyên tỉ lệ 0.842 trước/sau.

## Việc cần làm tiếp khi có base mesh thật

- Thay `compute_realistic_joints()`/`compute_realistic_radii()` bằng dữ liệu đọc trực tiếp từ
  mesh + shape key thật của hoạ sĩ (hiện đang dựng lại từ đầu bằng skeleton đơn giản).
- Thêm eye landmarks vào phép đo (anchor ② hiện chưa kiểm chứng được).
- `horizontal_keep` và `head_enlarge` trong `STYLIZE` là hệ số thẩm mỹ tự chọn — cần hoạ sĩ
  art direction duyệt lại con số cụ thể (0.88 và 1.55) khi có base mesh PSO2-style thật, giá
  trị ở đây chỉ để chứng minh cơ chế hoạt động.
- Phân loại tham số theo 4 nhóm identity/expression/cosmetic/equipment (đề xuất trong brief)
  chưa được code hoá thành type/schema trong `src/character/` — nên làm khi chuyển từ
  prototype sang production, để tránh cosmetic system vô tình ghi đè lên identity blend shape.
