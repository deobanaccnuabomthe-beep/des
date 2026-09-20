# Stylization Prototype v1.1 — phản hồi lại các giới hạn của v1

Tài liệu này ghi lại phần đã làm thêm sau khi review chỉ ra `docs/stylization-prototype-v1.md`
overclaim kết luận (gọi test silhouette-cực-đoan là "identity preservation"). v1.1 **không**
giải quyết hết mọi giới hạn được nêu — chỉ giải quyết những gì làm được mà không cần base mesh
mặt thật từ hoạ sĩ. Script: `tools/blender/generate_stylization_prototype_v1_1.py`.

## Đã sửa

**1. Test cực đoan quá dễ.** Thêm cặp C/D: cùng chiều cao (1.75m), cùng shoulder_scale,
cùng leg_length_scale — chỉ khác `face_width_scale` (1.05 vs 0.95) và `eye_spacing_scale`
(1.08 vs 0.94) và `eye_angle` (±3°). Đây là ca khó thật sự, không phải A/B thái cực như v1.

**Kết quả quan sát:** ở khung toàn thân (`hard_case_C_vs_D_stylized_front.png`), C và D **gần
như không phân biệt được bằng mắt** — đúng như dự đoán, vì khác biệt đầu vào rất nhỏ. Chỉ khi
zoom vào vùng đầu mới thấy được khác biệt nhỏ về khoảng cách/góc mắt. Đây là kết quả trung
thực, không phải thất bại: nó cho thấy method hiện tại **chưa đủ nhạy** để phân biệt hai người
gần giống nhau ở khung nhìn bình thường — một giới hạn thật cần hoạ sĩ và base mesh thật để
đánh giá lại (liệu chi tiết hình học mặt thật, không phải quả cầu proxy, có tạo khác biệt rõ
hơn).

**2. Không có hình học mắt.** Thêm marker hình cầu dẹt tại vị trí mắt, tham số hoá bằng
`eye_spacing_scale`, `eye_height_scale`, `eye_angle_deg`, `eye_depth_scale` — tính từ cùng
joint/radius đầu mà mesh dùng, nên marker di chuyển theo đúng phép stylize của đầu.

**Đây KHÔNG phải hình học mắt thật** — không có mí mắt, mống mắt, hốc mắt. Nó chỉ trả lời một
câu hỏi hẹp: "nếu tôi đặt hai điểm ở vị trí ước lượng của mắt, khoảng cách/góc giữa chúng có
còn tỉ lệ đúng sau khi đầu bị phóng to+nén không". Không trả lời được câu hỏi thật của anchor
② là "hai khuôn mặt thật có còn nhận ra nhau không".

**3. Ảnh không nhãn, khó phân biệt.** Mọi ảnh giờ có nhãn tên nhân vật + toàn bộ tham số đầu
vào, dùng Pillow ghi trực tiếp lên ảnh (`label_image()` trong script). Ảnh 1 và 2 ở v1 nhìn
giống nhau vì đúng là gần giống nhau thật (cùng camera, cùng bố cục 4 nhân vật, chỉ khác object
nào bị ẩn) — không phải lỗi, nhưng thiếu nhãn khiến khó review, giờ đã có nhãn.

**4. Thêm góc profile.** Mỗi nhân vật/biến thể giờ có cả `_front.png` và `_profile.png`, dùng
chung camera ortho + "Track To" constraint để tự động canh giữa bất kể góc nào.

## Giới hạn mới phát hiện khi làm góc profile

Ảnh profile bị nhiễu bởi tư thế A-pose: cánh tay dang ngang theo trục X, khi nhìn từ cạnh
(theo trục X) tay bị foreshorten chồng lên silhouette thân, tạo hình dạng kỳ dị chứ không phải
lỗi dựng mesh. Marker mắt xa camera cũng bị "lộ" ra ngoài viền đầu ở góc profile vì spacing mắt
đặt theo trục X trong khi đầu ở view này hẹp theo trục đó. Cả hai là hạn chế thật của việc dùng
proxy đơn giản + pose T/A-pose gốc, không phải điều production che giấu được — nên coi góc
profile ở version này chỉ dùng để debug silhouette đầu/vai, chưa dùng để đánh giá mặt.

## Vẫn CHƯA làm — đúng như review đã chỉ ra

- **Base mesh có topology mặt thật.** Đây là điểm chặn chính: không mesh mặt thật thì không có
  gò má, hàm, mũi, cung mày thật để test. Không thể làm phần này cho tới khi hoạ sĩ giao bài.
- **6–10 nhân vật.** Hiện có 4 (A, B, C, D). Mở rộng thêm dễ (chỉ thêm entry vào `CHARACTERS`
  trong script), nhưng không làm thêm ở bước này vì không tăng thêm giá trị chừng nào còn dùng
  proxy hình cầu cho mặt.
- **Ba lớp so sánh riêng (silhouette-only / face-only / full character).** Chưa làm — cần
  tóc/trang phục/màu để lớp "full character" có nghĩa, hiện chưa có asset nào.
- **Blind test người thật ghép cặp stylized ↔ gốc.** Không thể tự làm (cần người tham gia thật);
  bộ ảnh đã có nhãn tên+tham số nên nếu muốn chạy blind test, cần xoá nhãn (hoặc thay bằng ID
  ẩn danh) trước khi đưa cho người đánh giá — script hiện tại **cố tình** ghi nhãn để dễ debug,
  không phù hợp để dùng trực tiếp cho blind test.
- **Rig/pose/animation/trang phục.** Ngoài phạm vi bước này theo đúng thứ tự review đề xuất.

## Kết luận nên rút ra

So với v1, prototype này chỉ ra rằng: cơ chế stylize không tự động làm hai người gần giống
nhau trở nên PHÂN BIỆT hơn — nếu khác biệt đầu vào nhỏ, khác biệt đầu ra cũng nhỏ, đôi khi nhỏ
tới mức không đọc được ở khung nhìn thông thường. Đó là một phát hiện có giá trị, ngược hẳn với
ấn tượng "mọi thứ đều ổn" mà v1 vô tình tạo ra bằng cách chỉ test ca dễ. Câu hỏi "khuôn mặt thật
có đủ độ phân giải hình học để hai người giống nhau vẫn phân biệt được sau stylize" **vẫn mở**,
và chỉ trả lời được khi có base mesh mặt thật.
