# LIFE RPG — Đặc tả nhân vật 3D cho hoạ sĩ

_2026-09-17 · @Someone — nguyên văn từ `LIFE_RPG_Dac_ta_nhan_vat_3D_cho_hoa_si.pdf`_

## 1. Tổng quan dự án

LIFE RPG là ứng dụng di động (iOS và Android, React Native) biến hoạt động đời thực của
người dùng thành tiến trình của một nhân vật 3D. Ứng dụng có ba mảng: công việc hằng
ngày, thể hình, và tài chính cá nhân.

Nhân vật 3D là màn hình chính của ứng dụng. Người dùng mở app mỗi ngày để nhìn thấy
nhân vật của mình.

**Yêu cầu cốt lõi khiến việc này khác một nhân vật game thông thường:** hình thể nhân vật
phải biến đổi liên tục theo dữ liệu tập luyện thật — tập đều thì vai nở, eo thu, tay chân đầy
hơn. Biến đổi diễn ra dần qua nhiều tuần, không phải chuyển giữa vài mẫu dựng sẵn.

Vì vậy nhân vật không thể là một mesh tĩnh. Cần một **base mesh duy nhất kèm bộ blend
shapes (morph targets)** để code trong ứng dụng điều khiển bằng các giá trị số từ 0 đến 1.

**Môi trường chạy:** three.js, render thời gian thực trên điện thoại, gồm cả máy tầm trung
đời cũ. Hiệu năng là ràng buộc thật, không phải yêu cầu hình thức.

## 2. Định hướng nghệ thuật

Bán tả thực/anime stylized, tỉ lệ khoảng 3.5–4 đầu — không chibi hoá mắt và đầu như hướng
trước. Silhouette vẫn cần đọc rõ, nhưng khuôn mặt phải giữ đủ chi tiết hình học để phân
biệt được người chơi này với người chơi khác.

**Tham chiếu gần nhất:** character creator của PSO2/PSO2:NGS, cụ thể là hệ slider hình học
liên tục cho mặt — đây là tham chiếu kỹ thuật về độ phân giải morph, không phải để sao
chép phong cách thị giác PSO2. Màu sắc, trang phục và thế giới quan sẽ tự thiết kế riêng.

**Nên có:**
- Hình khối rõ ràng, đọc được silhouette ngay cả ở kích thước nhỏ trên điện thoại
- Bề mặt màu phẳng hoặc chuyển màu rất nhẹ, hợp với shading đơn giản
- Khuôn mặt giữ đủ chi tiết hình học (hốc mắt, gò má, đường hàm) để phản ánh đặc điểm
  scan riêng của từng người — không dùng chung một khuôn mặt mẫu cho mọi người chơi
- Tỉ lệ khoảng 3.5 đến 4 đầu cho toàn thân

**Không nên có:**
- Chi tiết giải phẫu tả thực: gân, mạch máu, nếp nhăn da
- Texture da có lỗ chân lông hoặc chi tiết ảnh chụp
- Tóc dựng từng sợi riêng lẻ (strand-based) — dùng nhóm clump/hair card theo chuẩn anime
  là đủ, không cần tốn hiệu năng cho strand thật
- Bất kỳ chi tiết nào không đọc được khi nhân vật cao 300 pixel trên màn hình

**Lưu ý quan trọng về bản quyền:** không sao chép nhân vật, trang phục hoặc tạo hình nhận
diện của Roblox, Nintendo hay bất kỳ sản phẩm nào khác. Tham chiếu là để chỉ mức độ
stylized, không phải để sao chép.

## 3. Yêu cầu kỹ thuật cho base mesh

| Hạng mục | Yêu cầu |
|---|---|
| Số tam giác | 8.000 đến 15.000 cho toàn thân, chưa tính tóc và trang phục |
| Topology | Quad thuần, chỉ dùng tam giác ở chỗ thật sự cần |
| Edge loop | Có loop rõ ràng quanh vai, ngực, eo, hông, bắp tay, đùi |
| UV | Một UV set duy nhất, không chồng lấn, có padding tối thiểu 8 pixel |
| Đơn vị | Mét, nhân vật cao đúng 1.75 m ở trạng thái mặc định |
| Trục | Y hướng lên, Z hướng về phía trước, khớp quy ước glTF |
| Gốc toạ độ | Ở giữa hai bàn chân, ngay mặt đất, toạ độ (0, 0, 0) |
| Tư thế | A-pose, tay hạ khoảng 45 độ so với phương ngang |
| Transform | Mọi transform đã freeze, scale bằng 1, rotation bằng 0 |
| Đối xứng | Mesh đối xứng qua trục X ở trạng thái mặc định |

**Về edge loop:** đây là yêu cầu quan trọng nhất trong bảng trên. Blend shapes thay đổi
hình thể chỉ chạy mượt khi mesh có đủ edge loop ở đúng chỗ cần phình ra hoặc thu lại. Mesh
thiếu loop quanh eo sẽ tạo nếp gãy khi morph.

**Không cần:** normal map nướng từ high-poly, displacement map, hoặc bất kỳ chi tiết bề mặt
nào đòi high-poly sculpt. Phong cách phẳng nên không dùng tới.

## 4. Blend shapes bắt buộc

Đây là phần quan trọng nhất của toàn bộ đặc tả. Mỗi blend shape là một biến dạng của base
mesh, ứng dụng sẽ trộn chúng bằng giá trị 0 đến 1 lấy từ dữ liệu người dùng.

**Quy ước chung:** trạng thái mặc định của mesh tương ứng giá trị 0 cho mọi blend shape.
Tên phải viết đúng chính xác như cột đầu, phân biệt hoa thường, vì code sẽ tìm theo tên.

| Tên blend shape | Biến dạng ở giá trị 1 | Nguồn dữ liệu trong app |
|---|---|---|
| `body_muscle` | Toàn thân tăng khối cơ: vai rộng, ngực dày, bắp tay và đùi nở | Tần suất và thời gian duy trì tập luyện |
| `body_fat` | Toàn thân tăng mỡ: bụng tròn, eo dày, mặt đầy hơn | Cân nặng so với chiều cao |
| `body_thin` | Toàn thân gầy đi: lộ xương đòn, chi mảnh, bụng hóp | Cân nặng thấp so với chiều cao |
| `shoulder_wide` | Riêng vai rộng ra, phần còn lại giữ nguyên | Khối lượng tập thân trên |
| `waist_narrow` | Riêng eo thu lại, tạo dáng chữ V | Tỉ lệ mỡ giảm |
| `chest_thick` | Riêng lồng ngực dày lên theo chiều trước sau | Khối lượng tập ngực |
| `arm_mass` | Riêng bắp tay và cẳng tay tăng khối | Khối lượng tập tay |
| `leg_mass` | Riêng đùi và bắp chân tăng khối | Khối lượng tập chân |
| `height_tall` | Kéo dài chân và thân, giữ tỉ lệ đầu | Chiều cao người dùng nhập |
| `height_short` | Rút ngắn chân và thân, giữ tỉ lệ đầu | Chiều cao người dùng nhập |

**Ba yêu cầu bắt buộc về chất lượng:**
1. Mỗi blend shape phải chạy đẹp ở mọi giá trị trung gian, không chỉ ở 0 và 1. Kiểm tra ở
   0.25, 0.5 và 0.75.
2. Các blend shape phải trộn được với nhau mà không vỡ mesh. Trường hợp cần kiểm tra kỹ
   nhất là `body_muscle` 0.8 cộng `body_fat` 0.6 cộng `shoulder_wide` 1.0.
3. Không blend shape nào được làm mesh tự giao cắt hoặc lộn ngược pháp tuyến ở bất kỳ giá
   trị nào.

**Về cặp đối lập:** `body_fat` và `body_thin` là hai blend shape riêng chứ không phải một
thanh trượt hai chiều, vì hai hướng biến dạng này không đối xứng với nhau. Tương tự với
`height_tall` và `height_short`.

**Nếu chi phí là vấn đề:** bốn blend shape đầu tiên trong bảng là tối thiểu để chứng minh
concept. Sáu cái còn lại có thể làm ở giai đoạn sau.

## 4b. Blend shapes cho khuôn mặt

Ngoài phần thân, nhân vật còn cần "nhận diện được" khuôn mặt người dùng — không tả
thực, cùng mức độ Roblox hay Bitmoji, người quen nhìn vào nhận ra ngay đây là bạn. Ứng
dụng tự trích xuất điểm mốc trên khuôn mặt qua camera, xử lý ngay trên điện thoại, rồi quy
thành các tham số dưới đây để áp lên phần đầu của base mesh.

Cần thêm các blend shape sau trên vùng đầu/mặt, theo đúng nguyên tắc như bảng ở mục 4
— mặc định là 0, tên phải khớp chính xác:

| Tên blend shape | Biến dạng ở giá trị 1 |
|---|---|
| `face_wide` | Mặt rộng ra theo chiều ngang |
| `face_narrow` | Mặt thu hẹp theo chiều ngang |
| `jaw_square` | Hàm vuông và rõ góc hơn |
| `jaw_round` | Hàm tròn và mềm hơn |
| `eyes_wide_set` | Hai mắt cách xa nhau hơn |
| `eyes_close_set` | Hai mắt gần nhau hơn |
| `nose_wide` | Sống mũi và cánh mũi to hơn |
| `nose_narrow` | Sống mũi và cánh mũi thanh hơn |

Bốn cặp đối lập ở đây — `face_wide`/`face_narrow`, `jaw_square`/`jaw_round`,
`eyes_wide_set`/`eyes_close_set`, `nose_wide`/`nose_narrow` — áp dụng đúng quy tắc đã nói
ở mục 4: không được cùng lớn hơn 0, và phải chạy đẹp ở giá trị trung gian (0.25, 0.5, 0.75),
không chỉ ở 0 và 1.

**Không cần ở gói mặt này:** blend shape cho miệng cử động, lông mày, hay biểu cảm — nhân
vật không nói hay diễn cảm xúc, chỉ cần đúng tỉ lệ khuôn mặt tĩnh.

**Nên hỏi giá riêng ngay từ đầu, dù làm sau:** nếu để tới gói sau mới báo, hoạ sĩ có thể phải
dựng lại topology vùng đầu vì bản đầu không chừa đủ edge loop cho các biến dạng này —
tốn công hơn nhiều so với tính trước.

## 4c. Biên độ blend shape & tham chiếu phong cách

Hệ thống nhắm tới nhận diện danh tính qua hình học mặt, kiểu character creator PSO2 —
slider liên tục ánh xạ trực tiếp từ dữ liệu scan, không phải preset rời rạc. Vì vậy bảng blend
shape ở trên cần thêm yêu cầu về biên độ: khác biệt phải nhìn rõ ở các mức giữa (0.3–0.7),
không chỉ ở hai đầu 0 và 1.

Khi hoạ sĩ demo, xin xem tối thiểu 3 mức mỗi blend shape (ví dụ 0.3 / 0.6 / 1.0) thay vì chỉ 0
và 1 — test hai đầu không cho biết quãng giữa có đủ mượt và đủ phân biệt hay không.

**Tham chiếu tỉ lệ:** bán tả thực/anime stylized kiểu PSO2, khoảng 3.5–4 đầu, không chibi hoá
mắt/đầu như Blue Archive hay MapleStory 2 — hai style đó dựa vào tóc/trang phục để phân
biệt nhân vật hơn là hình học mặt, ngược với mục tiêu nhận diện của hệ thống này.

| Blend shape | Ưu tiên biên độ | Vì sao |
|---|---|---|
| `eyes_wide_set` / `eyes_close_set` | Cao | Khoảng cách hai mắt là yếu tố nhận diện mạnh nhất trong nhóm mặt |
| `face_wide` / `face_narrow` | Cao | Ảnh hưởng nhiều tới cảm nhận "giống ai" |
| `jaw_square` / `jaw_round` | Trung bình | Rõ ở giá trị cao, không cần nhạy ở vùng giữa |
| `nose_wide` / `nose_narrow` | Thấp | Biến dạng phụ, không phải yếu tố nhận diện chính |

## 5. Rig và animation

Rig humanoid tiêu chuẩn, giữ tối giản. Đề xuất khoảng 25 đến 30 xương:
- Cột sống: hips, spine, chest, neck, head
- Tay: shoulder, upper arm, forearm, hand cho mỗi bên
- Chân: thigh, shin, foot, toe cho mỗi bên
- Không cần xương ngón tay riêng ở V1, bàn tay là một khối

**Skin weight:** tối đa 4 xương ảnh hưởng lên một vertex. Đây là giới hạn của three.js trên di
động.

**Yêu cầu đặc biệt:** skin weight phải còn đúng khi blend shapes ở giá trị cao. Vai và eo là
hai chỗ dễ hỏng nhất — kiểm tra bằng cách bật `body_muscle` lên 1.0 rồi xoay vai và gập
người.

Animation cần giao, mỗi cái là một clip riêng trong cùng file:

| Tên clip | Độ dài | Mô tả |
|---|---|---|
| `idle` | 3 đến 4 giây, lặp liền mạch | Đứng thở nhẹ, thỉnh thoảng chớp mắt |
| `celebrate` | 2 giây, không lặp | Ăn mừng khi lên level hoặc hoàn thành mục tiêu |
| `showcase` | 4 giây, lặp | Xoay chậm để khoe trang phục, dùng ở màn hình shop |

Không cần animation đi, chạy, hay chiến đấu. Nhân vật chỉ đứng trên màn hình chính.

## 6. Trang phục và cosmetics

Người dùng kiếm điểm từ hành vi tài chính tốt, rồi mua quần áo áp lên nhân vật. Vì hình thể
nhân vật thay đổi liên tục, **quần áo phải co giãn theo**, không được xuyên qua da.

**Phương án bắt buộc:** mỗi món trang phục là một mesh riêng, dùng cùng bộ rig và **cùng
bộ blend shapes trùng tên** với base mesh. Khi ứng dụng trượt giá trị `body_muscle`, cả
thân người lẫn áo cùng phình ra.

Điều này có nghĩa mỗi món quần áo cũng cần đủ bộ blend shapes cùng tên. Đây là chi phí
thật, cần tính vào báo giá cho từng món.

Bộ trang phục mẫu cần giao cùng base mesh:
- Một áo thun ngắn tay
- Một quần dài
- Một đôi giày
- Một kiểu tóc

**Về việc ẩn phần thân bị che:** giao thêm một bản base mesh có group riêng cho thân trên,
thân dưới, cánh tay, cẳng chân. Ứng dụng sẽ ẩn phần bị quần áo che để tránh xuyên mesh và
tiết kiệm hiệu năng.

## 7. Texture và material

Vì phong cách phẳng nên texture giữ ở mức tối thiểu, ưu tiên hiệu năng trên di động.

| Hạng mục | Yêu cầu |
|---|---|
| Độ phân giải | 1024 x 1024 cho thân, 512 x 512 cho từng món trang phục |
| Bản đồ cần có | Base color duy nhất |
| Bản đồ không cần | Normal, roughness, metallic, ambient occlusion |
| Số material | Tối đa 2 cho base mesh: một cho da và một cho tóc |
| Định dạng | PNG, không nén mất dữ liệu |

**Về màu da:** giao base color map ở dạng trung tính, kèm hướng dẫn vùng nào trên UV là
da. Ứng dụng sẽ nhuộm màu da theo lựa chọn của người dùng bằng cách nhân màu trong
shader, nên hoạ sĩ không cần vẽ nhiều phiên bản màu da.

**Tương tự với trang phục:** mỗi món giao một map, ứng dụng đổi màu bằng shader để tạo
nhiều biến thể từ một asset. Đây là cách giảm mạnh chi phí làm cosmetics về sau, nên hãy
thiết kế UV với điều này trong đầu.

## 8. Bàn giao và nghiệm thu

File cần nhận:
1. **File `.glb` chính** — base mesh, rig, toàn bộ blend shapes, animation clips, texture
   nhúng sẵn
2. **File `.glb` riêng cho mỗi món trang phục** — kèm blend shapes trùng tên
3. **File gốc** — `.blend` hoặc `.ma`, để sửa về sau mà không phụ thuộc hoạ sĩ
4. **Texture rời** — PNG ở độ phân giải gốc

Định dạng glTF/GLB là bắt buộc vì three.js đọc trực tiếp. Không nhận FBX làm file bàn giao
chính.

**Checklist nghiệm thu trước khi thanh toán đợt cuối:**
- [ ] File `.glb` mở được bằng trình xem glTF trực tuyến, không báo lỗi
- [ ] Tên blend shapes khớp chính xác bảng ở mục 4, phân biệt hoa thường
- [ ] Mỗi blend shape chạy đẹp ở 0.25, 0.5, 0.75, không chỉ ở 0 và 1
- [ ] Tổ hợp `body_muscle` 0.8 cộng `body_fat` 0.6 cộng `shoulder_wide` 1.0 không vỡ mesh
- [ ] Không vertex nào tự giao cắt hay lộn pháp tuyến ở bất kỳ tổ hợp nào
- [ ] Skin weight còn đúng khi blend shapes ở mức cao
- [ ] Ba animation clip đều có, `idle` và `showcase` lặp liền mạch
- [ ] Trang phục co giãn khớp thân người ở mọi giá trị blend shape, không xuyên da
- [ ] Số tam giác nằm trong ngưỡng đã nêu ở mục 3
- [ ] Nhân vật cao đúng 1.75 m, gốc toạ độ ở giữa hai bàn chân

**Đề nghị chia thanh toán theo ba đợt:** ký hợp đồng, duyệt base mesh trước khi làm blend
shapes, và nghiệm thu cuối. Đợt giữa quan trọng vì sửa topology sau khi đã làm blend shapes
rất tốn công.

## 9. Phạm vi công việc

Nếu ngân sách hạn chế, đây là thứ tự ưu tiên để hỏi giá theo từng gói.

**Gói tối thiểu — đủ để chứng minh concept:**
- Base mesh nam hoặc nữ, một giới tính
- Bốn blend shapes: `body_muscle`, `body_fat`, `body_thin`, `shoulder_wide`
- Rig cơ bản, một animation `idle`
- Một bộ trang phục mẫu

**Gói đầy đủ cho V1:**
- Thêm sáu blend shapes còn lại
- Thêm hai animation `celebrate` và `showcase`
- Bốn món trang phục như mục 6

**Gói mặt (hỏi giá riêng, xem mục 4b):**
- Tám blend shape cho khuôn mặt như bảng ở mục 4b
- Không cần thêm rig, animation hay texture riêng — dùng chung với base mesh

**Để sau, không cần ở V1:**
- Base mesh giới tính thứ hai
- Nhiều kiểu tóc
- Bộ cosmetics mở rộng

**Câu hỏi nên hỏi hoạ sĩ trước khi chốt:**
1. Bạn đã làm blend shapes cho biến đổi hình thể bao giờ chưa? Cho xem ví dụ.
2. Bạn xuất glTF/GLB có blend shapes và animation thường xuyên không?
3. Thời gian dự kiến cho gói tối thiểu là bao lâu?
4. Có bao nhiêu vòng chỉnh sửa trong báo giá?

Câu đầu tiên là quan trọng nhất. Nhiều hoạ sĩ 3D giỏi dựng nhân vật tĩnh nhưng chưa từng
làm blend shapes biến đổi hình thể, và đó chính là phần lõi của dự án này.
