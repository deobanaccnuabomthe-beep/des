# Stylization Prototype v1 — technical feasibility test (không phải bằng chứng identity)

**Kết luận chính xác của thử nghiệm này:** silhouette của hai cấu hình cơ thể **cực đoan**
(rất khác nhau về chiều cao/vai/mỡ/chân/mặt) không bị xoá bởi phép nén tỉ lệ "soft chibi anime"
(~3.75 đầu). Thử nghiệm **chưa** chứng minh rằng nhận dạng khuôn mặt hay danh tính một người
thật được bảo toàn — xem mục "Giới hạn" bên dưới để biết chính xác cái gì chưa được kiểm chứng.

Ban đầu tài liệu này viết là "kiểm tra identity preservation", cách gọi đó quá mạnh so với
những gì được test. A và B là hai cực đối lập nên bài test khá dễ; không có mắt/mũi/miệng/gò
má/hàm thật; không có tóc/trang phục/màu — những yếu tố có thể lấn át cảm nhận khuôn mặt trong
thực tế; chưa thử hai người gần giống nhau; chưa thử nhiều góc camera/pose/ánh sáng. Giữ
nguyên phần dưới đây làm biên bản kỹ thuật, đã sửa lại các chỗ diễn giải quá đà.

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

**Sửa lại một chỗ diễn giải sai:** đây không phải một affine transform duy nhất cho toàn thân
— nó phóng to đầu quanh một tâm cục bộ, nén thân/chân theo một hệ số khác, tăng độ tròn, và xử
lý từng vùng khớp riêng. Vì `stylize()` áp cùng công thức đó cho cả A và B, các tỉ lệ đo được
(bảng dưới) gần như chắc chắn được giữ — **đây là bằng chứng script chạy đúng ý đồ code, không
phải một phép kiểm chứng độc lập rằng thuật toán "bảo toàn identity"**. Nói cách khác: số liệu
đẹp phần lớn vì thuật toán được viết ra để giữ đúng các tham số đem ra đo — kết luận có giá trị
duy nhất ở đây là "cơ chế không tự phá vỡ các tỉ lệ nó được thiết kế để giữ", không hơn.

Điều thực sự cần đánh giá là bằng mắt (ảnh dưới) và trong trường hợp khó hơn — hai người
*gần giống nhau* — chứ không phải hai cực đối lập như A/B ở đây.

## Kết quả đo được

`assets/characters/stylization_prototype/identity_preservation_report.json`:

| Chỉ số | A thật | B thật | Tỉ lệ A/B | A stylized | B stylized | Tỉ lệ A/B |
|---|---|---|---|---|---|---|
| Chiều cao | 1.586 m | 1.884 m | 0.842 | 1.249 m | 1.483 m | 0.842 |
| Độ rộng vai | 0.289 m | 0.391 m | 0.739 | 0.254 m | 0.344 m | 0.738 |
| Độ rộng mặt | 0.288 m | 0.184 m | 1.565 | 0.499 m | 0.319 m | 1.564 |
| Độ dài chân | 0.684 m | 1.042 m | 0.656 | 0.457 m | 0.696 m | 0.656 |
| Tỉ lệ đầu/thân | 7.38 | 7.38 | — | 3.75 | 3.75 | — |

Tỉ lệ A/B gần như không đổi trước/sau stylize ở mọi chỉ số — như đã nói ở trên, đây là hệ quả
của cách viết `stylize()`, không phải phát hiện bất ngờ. Bằng mắt (xem ảnh dưới), khác biệt vẫn
đọc được rõ dù cả hai đã co về 3.75 đầu — **nhưng A và B là hai cực đối lập nên đây là bài test
dễ**; chưa chứng minh gì cho trường hợp hai người dáng người gần giống nhau (xem Prototype v1.1
bên dưới).

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

## Tiếp theo: xem `docs/stylization-prototype-v1.1.md`

v1.1 thêm cặp nhân vật gần giống nhau (ca khó hơn A/B), landmark mắt proxy, góc profile, và
nhãn trên ảnh — trực tiếp trả lời các giới hạn được chỉ ra ở review của v1.

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
