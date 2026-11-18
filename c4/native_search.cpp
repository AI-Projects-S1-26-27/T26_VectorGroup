// Optional heuristic search accelerator. Owner: Rujuta. Same horizon and
// full-window root scoring as c4/search.py; no selective depth reductions.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <deque>
#include <unordered_map>
#include <vector>

#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
using U = uint64_t;
using Clock = std::chrono::steady_clock;
constexpr int WIN=100000, INF=101000, EXACT=0, LOWER=1, UPPER=2;
constexpr U BOARD=U(63) | (U(63)<<7) | (U(63)<<14) | (U(63)<<21) |
                  (U(63)<<28) | (U(63)<<35) | (U(63)<<42);
constexpr U BOTTOM=U(1) | (U(1)<<7) | (U(1)<<14) | (U(1)<<21) |
                   (U(1)<<28) | (U(1)<<35) | (U(1)<<42);
constexpr int CENTER[7]={3,2,4,1,5,0,6};
struct Entry { int depth,value,flag,move; };
struct Table {
    size_t capacity;
    std::unordered_map<U,Entry> entries;
    std::deque<U> fifo;
    U probes=0,hits=0,stores=0;
    explicit Table(size_t n):capacity(n) { entries.reserve(n); }
    bool probe(U key,Entry& e) {
        ++probes;
        auto it=entries.find(key);
        if(it==entries.end()) return false;
        ++hits; e=it->second; return true;
    }
    void store(U key,Entry e) {
        auto it=entries.find(key);
        if(it!=entries.end()) {
            auto old=it->second;
            if(e.depth<old.depth || (e.depth==old.depth && old.flag==EXACT && e.flag!=EXACT)) return;
            it->second=e;
        } else {
            if(entries.size()>=capacity) { entries.erase(fifo.front());fifo.pop_front(); }
            entries.emplace(key,e);fifo.push_back(key);
        }
        ++stores;
    }
};
struct Move { int score=0,length=0; int pv[44]={}; };
struct Result { int status=0,depth=0,chosen=-1,static_score=0; U nodes=0; Move moves[7]; };
bool aligned(U b) {
    for(int shift:{7,6,8,1}) { U m=b&(b>>shift);if(m&(m>>(2*shift)))return true; }
    return false;
}
bool legal(U mask,int c) { return !(mask&(U(1)<<(7*c+5))); }
U played(U mask,int c) { return mask|(mask+(U(1)<<(7*c))); }
bool wins(U pos,U mask,int c) {
    U bit=(mask+(U(1)<<(7*c)))&(U(63)<<(7*c));
    return aligned(pos|bit);
}
const std::vector<U>& windows() {
    static const std::vector<U> value=[] {
        std::vector<U> out;
        for(int c=0;c<7;++c)for(int r=0;r<6;++r)
            for(auto delta:{std::pair<int,int>{1,0},{0,1},{1,1},{1,-1}}) {
                int dc=delta.first,dr=delta.second;
                if(c+3*dc>=0&&c+3*dc<7&&r+3*dr>=0&&r+3*dr<6) {
                    U w=0;for(int i=0;i<4;++i)w|=U(1)<<((c+i*dc)*7+r+i*dr);
                    out.push_back(w);
                }
            }
        return out;
    }();
    return value;
}
int evaluate(U pos,U mask) {
    U opp=pos^mask,center=U(63)<<21;
    int weights[5]={0,1,10,50,500};
    int score=3*(__builtin_popcountll(pos&center)-__builtin_popcountll(opp&center));
    for(U w:windows()) {
        int us=__builtin_popcountll(pos&w),them=__builtin_popcountll(opp&w);
        if(!them)score+=weights[us];if(!us)score-=weights[them];
    }
    for(int c:CENTER)if(legal(mask,c))score+=200*(int(wins(pos,mask,c))-int(wins(opp,mask,c)));
    return std::max(-9999,std::min(9999,score));
}
int to_tt(int value,int ply) {
    return value>WIN-43?value+ply:value<-(WIN-43)?value-ply:value;
}
int from_tt(int value,int ply) {
    return value>WIN-43?value-ply:value<-(WIN-43)?value+ply:value;
}
struct TimeUp {};
struct Searcher {
    Table* table;bool ordering;U nodes=0;
    Clock::time_point deadline;bool timed=false;
    std::vector<int> pv[44];
    Searcher(Table* t,bool o):table(t),ordering(o){}
    int negamax(U pos,U mask,int depth,int alpha,int beta,int ply) {
        ++nodes;
        if((nodes&63)==0&&timed&&Clock::now()>=deadline)throw TimeUp{};
        pv[ply].clear();
        int moves[7],n=0;
        for(int c:CENTER)if(legal(mask,c))moves[n++]=c;
        if(!n)return 0;
        for(int i=0;i<n;++i)if(wins(pos,mask,moves[i])) {
            pv[ply]={moves[i]};return WIN-(ply+1);
        }
        if(!depth)return evaluate(pos,mask);
        int original=alpha,tt_move=-1;
        U key=pos+mask;Entry entry;
        if(table&&table->probe(key,entry)) {
            tt_move=entry.move;
            if(entry.depth>=depth&&ply>1) {
                int value=from_tt(entry.value,ply);
                if(entry.flag==EXACT)return value;
                if(entry.flag==LOWER)alpha=std::max(alpha,value);else beta=std::min(beta,value);
                if(alpha>=beta)return value;
            }
        }
        if(ordering) {
            bool blocks[7]={};for(int i=0;i<n;++i)blocks[moves[i]]=wins(pos^mask,mask,moves[i]);
            auto rank=[&](int c) { return c==tt_move?0:blocks[c]?1:2; };
            std::stable_sort(moves,moves+n,[&](int a,int b){return rank(a)<rank(b);});
        } else if(tt_move>=0) {
            auto it=std::find(moves,moves+n,tt_move);
            if(it!=moves+n)std::rotate(moves,it,it+1);
        }
        int best=-INF,best_move=-1;
        for(int i=0;i<n;++i) {
            int c=moves[i];
            int score=-negamax(pos^mask,played(mask,c),depth-1,-beta,-alpha,ply+1);
            if(score>best) {
                best=score;best_move=c;
                if(score>alpha) {
                    alpha=score;pv[ply]={c};
                    pv[ply].insert(pv[ply].end(),pv[ply+1].begin(),pv[ply+1].end());
                    if(alpha>=beta)break;
                }
            }
        }
        if(table)table->store(key,{depth,to_tt(best,ply),best<=original?UPPER:best>=beta?LOWER:EXACT,best_move});
        return best;
    }
};
API void* c4_table_new(U capacity) { try{return new Table(capacity);}catch(...){return nullptr;} }
API void c4_table_free(void* p) { delete static_cast<Table*>(p); }
API void c4_table_clear(void* p) {
    auto& t=*static_cast<Table*>(p);t.entries.clear();t.fifo.clear();t.probes=t.hits=t.stores=0;
}
API int c4_table_probe(void* p,U key,int* out) {
    Entry e;if(!static_cast<Table*>(p)->probe(key,e))return 0;
    out[0]=e.depth;out[1]=e.value;out[2]=e.flag;out[3]=e.move;return 1;
}
API void c4_table_store(void* p,U key,int depth,int value,int flag,int move) {
    static_cast<Table*>(p)->store(key,{depth,value,flag,move});
}
API void c4_table_stats(void* p,U* out) {
    auto& t=*static_cast<Table*>(p);out[0]=t.entries.size();out[1]=t.probes;out[2]=t.hits;out[3]=t.stores;
}
API void c4_table_counters(void* p,U probes,U hits,U stores) {
    auto& t=*static_cast<Table*>(p);t.probes=probes;t.hits=hits;t.stores=stores;
}
API U c4_result_size() { return sizeof(Result); }
API int c4_evaluate(U pos,U mask) { return evaluate(pos,mask); }
API int c4_search(U pos,U mask,double seconds,int max_depth,void* table,int ordering,Result* out) {
    try {
        *out=Result{};
        if(aligned(pos^mask)||__builtin_popcountll(mask)==42||max_depth<1)return 1;
        Searcher s(static_cast<Table*>(table),ordering!=0);
        auto start=Clock::now();
        s.deadline=start+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
        out->static_score=evaluate(pos,mask);
        int root[7],n=0;for(int c:CENTER)if(legal(mask,c))root[n++]=c;
        int last=std::min(max_depth,42-__builtin_popcountll(mask));
        for(int depth=1;depth<=last;++depth) {
            if(depth>1&&Clock::now()>=s.deadline)break;
            s.timed=depth>1;
            Move current[7];
            try {
                for(int i=0;i<n;++i) {
                    int c=root[i];auto& move=current[c];
                    if(wins(pos,mask,c)) { move.score=WIN-1;move.length=1;move.pv[0]=c; }
                    else {
                        move.score=-s.negamax(pos^mask,played(mask,c),depth-1,-INF,INF,1);
                        move.pv[0]=c;move.length=1;
                        for(int col:s.pv[1])move.pv[move.length++]=col;
                    }
                }
            } catch(TimeUp&) { break; }
            std::copy(current,current+7,out->moves);out->depth=depth;
            int chosen=root[0];for(int i=1;i<n;++i)if(current[root[i]].score>current[chosen].score)chosen=root[i];
            out->chosen=chosen;
            if(std::abs(current[chosen].score)>WIN-43)break;
        }
        out->nodes=s.nodes;return 0;
    } catch(...) { return 2; }
}
