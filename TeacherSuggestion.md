1. 
開始前我先定義一下用詞:
password: 原本的明碼密碼
salt: 呃... 就是salt
hashing_algorithm: 例如argon2id, bcrypt, sha, md5等...
hash: hashing_algorithm的輸出
所以 hash = hashing_algorithm(salt+password)
以前的標準做法是在一個獨立的table裡存salt和hash:

table_user as tu:
    id (PK)
    email (unique)

table_credential as tc:
    id (PK)
    user_id (FK)
    stored_salt
    stored_hash

然後在使用者登入的階段，把使用者輸入的password去和tc.stored_hash做檢查:
if tu.email is found then
    on tc.user_id = tu.id
    if hashing_algorithm(tc.stored_salt+password) == tc.stored_hash then
        log in successful
    else
        password incorrect
else
    user not found.

然而現在新的標準是將salt和hash寫在一個字串裡。這裡我們以argon2id為例。
在這裡我一次說明argon2id的基本運作邏輯。

在註冊階段，系統把password交給argon2id:

hash = argon2id(password)

在這個步驟裡，argon2id會自己以CSPRNG生成一串二進位的salt (以下稱salt_binary)。
因此 hash = argon2id(password) 這裡真正發生的是:

hash_binary = argon2id(salt_binary + password)

而這裡輸出的hash_binary也是一長串的二進位資料。

因為salt_binary和hash_binary很長且無法給人閱讀，所以會用編碼器(encoder)翻譯成我們可閱讀的文字符號。以Python的argon2-cffi套件為例，它預設的編碼器是標準的Base64 Encoder。

經過編碼的hash就會長的如下:
$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$b3V0cHV0aGFzaA

argon2id是以"$"符號當作切斷符號(delimiter)，所以上面的hash可以切成以下:
argon2id – 演算法 (The Algorithm)： 告知函式庫要使用 Argon2id 這個版本。
v=19 – 版本 (The Version)： 指定所使用的 Argon2 內部版本。
m=65536,t=3,p=4 – 參數 (The Parameters)： 用來建立hash的確切硬體設定（記憶體 Memory = 64MB、時間/迭代次數 Time/Iterations = 3、平行處理/執行緒 Parallelism/Threads = 4）。
c2FsdHNhbHQ – Salt： 系統產生的隨機salt，已透過 Base64 編碼。
b3V0cHV0aGFzaA – Hash： 最終生成的密碼hash，同樣已透過 Base64 編碼。
因此，回到剛才的註冊階段，系統把password交給argon2id:
hash = argon2id(password)

會得到一個字串:  $argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$b3V0cHV0aGFzaA

因此在table_credential就不需要stored_salt的欄位，只需要把上面的這個字串存進stored_hash的欄位。
table_credential:
    id (PK)
    user_id (FK)
    stored_hash (argon2id_hash)

之後在登入階段，將使用者登入時輸入的password交給argon2id去做比對:

argon2id.verify(tc.stored_hash, password)

argon2id.verify會自動擷取出tc.stored_hash字串裡的c2FsdHNhbHQ，然後檢查:

if argon2id(c2FsdHNhbHQ + password) == b3V0cHV0aGFzaA then
    log in successful
else
    incorrect password

希望以上說明對大家有幫助。
有不清楚的地方或誤植的內容，歡迎提出。

*上述argon2id.verify的過程會把 c2FsdHNhbHQ 和 b3V0cHV0aGFzaA 解碼回二進位做hasing和比對。
2. 
因此，在本專案的RAG pipeline中：
資料庫的正規化是
幫助資料正確儲存與使用
讓queries.py更有效率對資料庫做CRUD
進而幫助tool calling的操作更有結構和效率
Pipeline資料的正規化是
幫助資料流動時，不同function和元件有共通的資料結構和語彙
結構化tool calling的操作與降低因LLM幻覺導致的錯誤率
優化LLM消化資料和prompt
有效隱藏資料原始樣貌
當然，RAG的normalisation還有更多細節(包含data ingestion->data modeling的設計)，只是已經遠遠超出資料庫這門課的範圍。這也是為什麼我沒有過度解釋上面的細節，還有為什麼專案最後只停留在一個題目上，因為每一個新的題目都需要對pipeline做一次對應的normalisation。

======================

最後回應vector DB和metadata做正規化的問題。
【原則】上，在vector DB裡的metadata是沒有資料庫正規化的操作。
真正的正規化是設計好有邏輯和結構的metadata後 (很多是JSON，JSONB格式) ，存進vector DB。以下面例子來說(超簡化範例)，兩個文件各自帶有keyword和category，而這兩個metadata的值是在外部定義好的選擇與結構。vector DB只是存進去而已。vector DB幾乎都可以對embedding和metadata做indexing的動作，進而提升檢索的效能。這類的metadata通常是為了檢索時可做更精準的filtering而生。

但如果metadata是為了"擴增"原本文字的內容，譬如摘要、概念總結等，這些metadata則有時候會轉成embedding存在另一個欄位，甚至可能和原文接在一起去embedding。

id	title	embedding	keywords	category
1	xxx	[vector 1]	["refund", "ticket", "delay"]	["ticketing"]
2	yyy	[vector 2]	["ticket", "booking", "cancel"]	["ticketing"]
