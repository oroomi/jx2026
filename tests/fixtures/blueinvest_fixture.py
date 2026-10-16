"""Synthetic BlueInvest pages for tests. All names are invented; nothing here is a real company fact."""


def list_page(ids_titles):
    blocks = "".join(
        f'<div class="stripe-content"><div class="tb-name"><h4><a href="https://example.invalid/pipeline_front.html?action=detail&amp;'
        f'params%5Bshow%5D=comp&amp;params%5Bother_id%5D={i}">{t}</a></h4><div class="subtext">fixture</div></div></div>'
        for i, t in ids_titles
    )
    return f"<html><body>{blocks}</body></html>"


def detail_page(title="Fixture Project", company="Fixture Oy", country="Finland", trl="TRL 5 - Technology validated in relevant environment",
                sector="Fixture sector", date_label=None, date_value=None):
    trl_block = (f"<div class=\"catalogue-field\"><span class='catalogue-detail-label '>TRL</span><br />"
                 f"<div class=\"list1x\"><ul class=\"keywords-catalogue-view clearfix\"><li>{trl}</li></ul></div><br /></div><hr>") if trl else ""
    date_block = (f"<div class=\"catalogue-field\"><span class='catalogue-detail-label '>{date_label}</span><br />{date_value}<br /></div><hr>"
                  if date_label else "")
    return (
        "<html><body><div class='catalogue-detail__content'>"
        f"<div class=\"catalogue-field\">{title}<br /></div><hr>"
        "<div class=\"catalogue-field\">Fixture description &amp; text.<br /><br /></div>"
        f"<div class=\"catalogue-field\"><div class=\"list1x\"><ul class=\"keywords-catalogue-view clearfix\"><li>{sector}</li></ul></div><br /></div>"
        f"<span class='catalogue-detail-label '>Company behind project</span><br /><a>{company}</a><br /><br />"
        f"<div class=\"catalogue-field\">{country}<br /><br /></div><hr>"
        f"{trl_block}{date_block}"
        "</div></div></span></p>Back to Pipeline</body></html>"
    )
